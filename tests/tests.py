# pylint: disable=missing-docstring,protected-access,invalid-name

from io import BytesIO
from unittest.mock import patch, MagicMock
import time
from django.test import TestCase

from s3cache import AmazonS3Cache

class S3CacheTestCase(TestCase):
    pass

class CacheConfigurationTest(S3CacheTestCase):
    def test_old_style_options(self):
        """
            Test django-storages < 1.1.8 options syntax, which
            needs to be translated to latest syntax
        """
        cache = AmazonS3Cache(
            None, # location
            {
                'BACKEND': 's3cache.AmazonS3Cache',
                'OPTIONS' : {
                    'ACCESS_KEY_ID' : 'access_key_old',
                    'SECRET_ACCESS_KEY' : 'secret_key_old',
                    'STORAGE_BUCKET_NAME': 'bucket_old',
                }
            }
        )

        self.assertEqual(cache._options['access_key'], 'access_key_old')
        self.assertEqual(cache._options['secret_key'], 'secret_key_old')
        self.assertEqual(cache._options['bucket_name'], 'bucket_old')

    def test_new_style_options(self):
        """
            Test django-storages >= 1.1.8 options syntax
        """
        cache = AmazonS3Cache(
            None, # location
            {
                'BACKEND': 's3cache.AmazonS3Cache',
                'OPTIONS' : {
                    'ACCESS_KEY' : 'access_key_new',
                    'SECRET_KEY' : 'secret_key_new',
                    'BUCKET_NAME': 'bucket_new',
                }
            }
        )

        self.assertEqual(cache._options['access_key'], 'access_key_new')
        self.assertEqual(cache._options['secret_key'], 'secret_key_new')
        self.assertEqual(cache._options['bucket_name'], 'bucket_new')

    def test_mixed_style_options(self):
        """
            Test MIXED options syntax (upgrade leftovers)
        """
        cache = AmazonS3Cache(
            None, # location
            {
                'BACKEND': 's3cache.AmazonS3Cache',
                'OPTIONS' : {
                    'ACCESS_KEY_ID' : 'access_key_mix', # old
                    'SECRET_KEY' : 'secret_key_mix',
                    'STORAGE_BUCKET_NAME': 'bucket_mix', # old
                }
            }
        )

        self.assertEqual(cache._options['access_key'], 'access_key_mix')
        self.assertEqual(cache._options['secret_key'], 'secret_key_mix')
        self.assertEqual(cache._options['bucket_name'], 'bucket_mix')

    def test_lowercase_new_style_options(self):
        """
            Test django-storages >= 1.1.8 options syntax in lower case.
            django-s3-cache v1.3 README was showing lowercase names for the options
            but those were overriden by the backward compatibility code and
            set to None. The issue comes from s3cache automatically converting
            everything to lower case before passing it down to django-storages
            which uses only lower case names for its class attributes.

            Documentation was updated in 3aaa0f254a2e0e389961b2112a00d3edf3e1ee90

            Real usage of lower case option names:
            https://github.com/atodorov/django-s3-cache/issues/2#issuecomment-65423398
        """
        cache = AmazonS3Cache(
            None, # location
            {
                'BACKEND': 's3cache.AmazonS3Cache',
                'OPTIONS' : {
                    'access_key' : 'access_key_low',
                    'secret_key' : 'secret_key_low',
                    'bucket_name': 'bucket_low',
                }
            }
        )

        self.assertEqual(cache._options['access_key'], 'access_key_low')
        self.assertEqual(cache._options['secret_key'], 'secret_key_low')
        self.assertEqual(cache._options['bucket_name'], 'bucket_low')

# pylint: disable=no-member,too-many-public-methods
class FunctionalTests(TestCase):
    def _dump_object(self, value, timeout=None):
        io_obj = BytesIO()
        io_obj.write(self.cache._dump_object(value, timeout))
        io_obj.seek(0)
        return io_obj

    def setUp(self):
        self.cache = AmazonS3Cache(None, {})

    def test_is_expired_with_expired_object(self):
        obj = self._dump_object('TEST', -1)
        with patch.object(AmazonS3Cache, '_delete'):
            self.assertTrue(self.cache._is_expired(obj, 'dummy file name'))

    def test_is_expired_with_valid_object(self):
        obj = self._dump_object('TEST', +10)
        with patch.object(AmazonS3Cache, '_delete'):
            self.assertFalse(self.cache._is_expired(obj, 'dummy file name'))

    def test_max_entries_great_than_1000(self):
        cache = AmazonS3Cache(None, {'OPTIONS': {'MAX_ENTRIES': 1001}})
        self.assertEqual(cache._max_entries, 1000)

    def test_max_entries_less_than_1000(self):
        cache = AmazonS3Cache(None, {'OPTIONS': {'MAX_ENTRIES': 200}})
        self.assertEqual(cache._max_entries, 200)

    def test_has_key_with_valid_key_and_non_expired_object(self):
        obj = self._dump_object('TEST', +10)
        with patch.object(self.cache._storage, 'open', return_value=obj):
            self.assertTrue(self.cache.has_key('my-key'))

    def test_has_key_with_valid_key_and_expired_object(self):
        obj = self._dump_object('TEST', -1)
        with patch.object(self.cache._storage, 'open', return_value=obj), \
             patch.object(AmazonS3Cache, '_delete'):
            self.assertFalse(self.cache.has_key('my-key'))

    def test_has_key_with_invalid_key(self):
        with patch.object(self.cache._storage, 'open', side_effect=IOError):
            self.assertFalse(self.cache.has_key('my-key'))

    def test_add_with_existing_key(self):
        with patch.object(self.cache, 'has_key', return_value=True):
            self.assertFalse(self.cache.add('my-key', 'TEST'))

    def test_add_with_non_existing_key(self):
        with patch.object(self.cache, 'has_key', return_value=False), \
             patch.object(self.cache, '_cull') as cull_mock, \
             patch.object(self.cache._storage, 'save') as save_mock:
            self.assertTrue(self.cache.add('my-key', 'TEST'))
            self.assertEqual(cull_mock.call_count, 1)
            self.assertEqual(save_mock.call_count, 1)

    def test_set_storage_raises_exception(self):
        with patch.object(self.cache._storage, 'save', side_effect=IOError), \
             patch.object(self.cache, '_cull'):
            # doesn't raise an exception
            self.cache.set('my-key', 'TEST')

    def test_get_valid_key_non_expired_object(self):
        obj = self._dump_object('TEST', +10)
        with patch.object(self.cache._storage, 'open', return_value=obj):
            self.assertEqual(self.cache.get('my-key'), 'TEST')

    def test_get_valid_key_expired_object(self):
        obj = self._dump_object('TEST', -1)
        with patch.object(self.cache._storage, 'open', return_value=obj), \
             patch.object(AmazonS3Cache, '_delete'):
            self.assertEqual(self.cache.get('my-key'), None)

    def test_get_after_waiting_the_object_to_expire(self):
        obj = self._dump_object('TEST', 2)
        # wait for object expiration
        # when mutation testing is used
        # time.time() * timeout instead of time.time() + timeout mutation
        # will set the expiration date in the future
        time.sleep(3)
        with patch.object(self.cache._storage, 'open', return_value=obj), \
             patch.object(AmazonS3Cache, '_delete'):
            self.assertEqual(self.cache.get('my-key'), None)

    def test_get_storage_raises_exception(self):
        with patch.object(self.cache._storage, 'open', side_effect=IOError):
            self.assertEqual(self.cache.get('my-key'), None)

    def test_delete(self):
        with patch.object(self.cache._storage, 'delete') as delete_mock:
            self.cache.delete('my-key')
            self.assertEqual(delete_mock.call_count, 1)

    def test_delete_storage_raises_exception(self):
        with patch.object(self.cache._storage, 'delete', side_effect=IOError):
            # doesn't raise an exception
            self.cache.delete('my-key')

    def test_clear(self):
        cache = AmazonS3Cache(None, {})
        cache._max_entries = 10
        cache._cull_frequency = 3
        key_list = [
            {'Key': '1'}, {'Key': '2'}, {'Key': '3'}, {'Key': '4'},
            {'Key': '5'}, {'Key': '6'}, {'Key': '7'}, {'Key': '8'},
            {'Key': '9'}, {'Key': '0'}
        ]

        mock_bucket = MagicMock()
        mock_bucket.name = 'test-bucket'

        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {'Contents': [{'Key': k['Key']} for k in key_list]}

        with patch.object(cache._storage, 'bucket', mock_bucket), \
             patch.object(cache._storage, 'connection') as mock_conn:
            mock_conn.meta.client = mock_client
            cache.clear()
            # clear() calls _cull(0) which lists objects twice (once for count check, once for deletion)
            self.assertEqual(mock_client.list_objects_v2.call_count, 2)
            self.assertEqual(mock_client.delete_objects.call_count, 1)
            # all keys were deleted
            mock_client.delete_objects.assert_called_once()
            call_args = mock_client.delete_objects.call_args
            self.assertEqual(call_args[1]['Bucket'], 'test-bucket')
            self.assertEqual(len(call_args[1]['Delete']['Objects']), len(key_list))


    def test_clear_bucket_raises_exception(self):
        mock_bucket = MagicMock()
        mock_bucket.name = 'test-bucket'

        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {'Contents': [{'Key': '1'}, {'Key': '2'}, {'Key': '3'}]}
        mock_client.delete_objects.side_effect = OSError

        with patch.object(self.cache._storage, 'bucket', mock_bucket), \
             patch.object(self.cache._storage, 'connection') as mock_conn:
            mock_conn.meta.client = mock_client
            self.cache.clear()

    def test_num_entries(self):
        mock_bucket = MagicMock()
        mock_bucket.name = 'test-bucket'

        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {'Contents': [{'Key': '1'}, {'Key': '2'}, {'Key': '3'}]}

        with patch.object(self.cache._storage, 'bucket', mock_bucket), \
             patch.object(self.cache._storage, 'connection') as mock_conn:
            mock_conn.meta.client = mock_client
            self.assertEqual(self.cache._num_entries, 3)

    def test_cull_without_max_entries(self):
        cache = AmazonS3Cache(None, {})
        cache._max_entries = 0

        mock_bucket = MagicMock()
        mock_client = MagicMock()

        with patch.object(cache._storage, 'bucket', mock_bucket), \
             patch.object(cache._storage, 'connection') as mock_conn:
            mock_conn.meta.client = mock_client
            cache._cull()
            self.assertEqual(mock_client.list_objects_v2.call_count, 0)

    def test_cull_with_num_entries_less_than_max_entries(self):
        mock_bucket = MagicMock()
        mock_bucket.name = 'test-bucket'

        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {'Contents': [{'Key': '1'}, {'Key': '2'}, {'Key': '3'}]}

        with patch.object(self.cache._storage, 'bucket', mock_bucket), \
             patch.object(self.cache._storage, 'connection') as mock_conn:
            mock_conn.meta.client = mock_client
            self.cache._cull()
            self.assertEqual(mock_client.list_objects_v2.call_count, 1)
            self.assertEqual(mock_client.delete_objects.call_count, 0)

    def test_cull_with_num_entries_great_than_max_entries_cull_frequency_0(self):
        cache = AmazonS3Cache(None, {})
        cache._max_entries = 5
        cache._cull_frequency = 0
        key_list = [
            {'Key': '1'}, {'Key': '2'}, {'Key': '3'}, {'Key': '5'},
            {'Key': '6'}, {'Key': '7'}, {'Key': '8'}, {'Key': '9'}, {'Key': '0'}
        ]

        mock_bucket = MagicMock()
        mock_bucket.name = 'test-bucket'

        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {'Contents': [{'Key': k['Key']} for k in key_list]}

        with patch.object(cache._storage, 'bucket', mock_bucket), \
             patch.object(cache._storage, 'connection') as mock_conn:
            mock_conn.meta.client = mock_client
            cache._cull()
            self.assertEqual(mock_client.list_objects_v2.call_count, 2)
            self.assertEqual(mock_client.delete_objects.call_count, 1)
            # when cull_frequency == 0 it means to delete all keys
            call_args = mock_client.delete_objects.call_args
            self.assertEqual(len(call_args[1]['Delete']['Objects']), len(key_list))

    def test_cull_with_num_entries_great_than_max_entries_cull_frequency_3(self):
        cache = AmazonS3Cache(None, {})
        cache._max_entries = 5
        cache._cull_frequency = 3
        key_list = [
            {'Key': '1'}, {'Key': '2'}, {'Key': '3'}, {'Key': '4'},
            {'Key': '5'}, {'Key': '6'}, {'Key': '7'}, {'Key': '8'},
            {'Key': '9'}, {'Key': '0'}
        ]
        delete_list = [{'Key': '1'}, {'Key': '4'}, {'Key': '7'}, {'Key': '0'}]

        mock_bucket = MagicMock()
        mock_bucket.name = 'test-bucket'

        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {'Contents': [{'Key': k['Key']} for k in key_list]}

        with patch.object(cache._storage, 'bucket', mock_bucket), \
             patch.object(cache._storage, 'connection') as mock_conn:
            mock_conn.meta.client = mock_client
            cache._cull()
            self.assertEqual(mock_client.list_objects_v2.call_count, 2)
            self.assertEqual(mock_client.delete_objects.call_count, 1)
            # when cull_frequency != 0 it means to delete every Nth key
            call_args = mock_client.delete_objects.call_args
            self.assertEqual(call_args[1]['Delete']['Objects'], delete_list)

    def test_cull_bucket_get_all_keys_raises_exception(self):
        class MockAmazonS3Cache(AmazonS3Cache):
            def _get_num_entries(self):
                return 10
            _num_entries = property(_get_num_entries)

        cache = MockAmazonS3Cache(None, {})
        cache._max_entries = 5

        with patch.object(cache._storage, '_bucket') as _bucket:
            _bucket.configure_mock(**{
                'get_all_keys.side_effect': OSError
            })
            cache._cull()
            self.assertEqual(_bucket.get_all_keys.call_count, 1)
            self.assertEqual(_bucket.delete_keys.call_count, 0)

    def test_cull_bucket_delete_keys_raises_exception(self):
        cache = AmazonS3Cache(None, {})
        cache._max_entries = 5
        key_list = [
            {'Key': '1'}, {'Key': '2'}, {'Key': '3'}, {'Key': '5'},
            {'Key': '6'}, {'Key': '7'}, {'Key': '8'}, {'Key': '9'}, {'Key': '0'}
        ]

        mock_bucket = MagicMock()
        mock_bucket.name = 'test-bucket'

        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {'Contents': [{'Key': k['Key']} for k in key_list]}
        mock_client.delete_objects.side_effect = OSError

        with patch.object(cache._storage, 'bucket', mock_bucket), \
             patch.object(cache._storage, 'connection') as mock_conn:
            mock_conn.meta.client = mock_client
            cache._cull()
            self.assertEqual(mock_client.list_objects_v2.call_count, 2)
            self.assertEqual(mock_client.delete_objects.call_count, 1)
