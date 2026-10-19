from utilities.email_backend import _SMTP


def test_login_skips_cram_md5():
    smtp = _SMTP()  # no host: does not connect
    smtp.ehlo_resp = b"ok"
    smtp.esmtp_features["auth"] = " LOGIN CRAM-MD5 PLAIN"
    used = []
    smtp.auth = lambda mechanism, *args, **kwargs: used.append(mechanism) or (235, b"ok")

    smtp.login("user", "key")

    assert used == ["PLAIN"]
