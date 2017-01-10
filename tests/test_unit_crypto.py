import pytest

from parsec.crypto.aes import AESCipher, AESCipherError
from os import urandom


class TestUnitCryptoAES:

    def setup_method(self):
        self.test_data = (b"Hellooow, I am a plaintext. "
                          b"I need to be encryoted to live a wonderful life")
        self.test_encrypted = (b"""\xae\xbe\xeah"\xbb?O\x03rpG\xcc\xa3N\xcb\xd3Am"""
                               b"""\x12\xe2\x1a\x81;\xcb{E\x0c1\xbdv\x1b1q\xe9\xe2\x04"""
                               b"""%\xd5\xfc\xbd\xbc\xf7\xf7~\'\\6-\x88\xb5\x05)="""
                               b"""\xb1/\xa2\xa7\xa1*O.Z\xb42\xdf\x05\xcd\x04\x82\\\x02D"""
                               b"""\xda\xa5oWRV\xa8\xc0`ut\\\\\xebd\xb4\xac\xbfJ/"""
                               b"""\xfd98\x94[2D\xa2\x0b?H\xec\x8a2""")
        self.test_iv = b"""\xae\xbe\xeah"\xbb?O\x03rpG\xcc\xa3N\xcb"""
        self.test_tag = b"""J/\xfd98\x94[2D\xa2\x0b?H\xec\x8a2"""
        self.test_key = (b"""\xb6\x12\xdc$\xe4\xc3\x03[J\xf7\xdbr\x17\xe1\xf5"""
                         b"""\xcf\x9d@%Y\xa2\xc5\xd6O\xbf>\xeb\xb0\xec"\x85|""")

    def test_aes_encrypt_good(self):
        key, enc = AESCipher.encrypt(self.test_data)
        assert key
        assert enc
        # 32 == Size of IV + size of AES-GCM tag
        assert len(enc) == 32 + len(self.test_data)
        assert self.test_data not in enc

    def test_aes_decrypt_good(self):
        dec = AESCipher.decrypt(self.test_encrypted, self.test_key)
        assert dec == self.test_data

    def test_aes_decrypt_bad_iv(self):
        new_enc = urandom(16) + self.test_encrypted[16:]
        with pytest.raises(AESCipherError) as e:
            AESCipher.decrypt(new_enc, self.test_key)
        assert str(e.value) == 'GMAC verification failed'

    def test_aes_decrypt_bad_tag(self):
        new_enc = self.test_encrypted[:-16] + urandom(16)
        with pytest.raises(AESCipherError) as e:
            AESCipher.decrypt(new_enc, self.test_key)
        assert str(e.value) == 'GMAC verification failed'

    def test_aes_decrypt_bad_key(self):
        with pytest.raises(AESCipherError) as e:
            AESCipher.decrypt(self.test_encrypted, urandom(32))
        assert str(e.value) == 'GMAC verification failed'

    def test_aes_decrypt_bad_key_length(self):
        with pytest.raises(AESCipherError) as e:
            AESCipher.decrypt(self.test_encrypted, urandom(31))
        assert str(e.value) == 'Cannot decrypt data'


class TestUnitCryptoRSA:
    # TODO
    pass
