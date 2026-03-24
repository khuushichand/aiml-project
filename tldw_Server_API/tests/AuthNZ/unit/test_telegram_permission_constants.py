from tldw_Server_API.app.core.AuthNZ import permissions as perms


def test_telegram_permission_constants_exist():
    assert perms.TELEGRAM_ADMIN == "telegram.admin"
    assert perms.TELEGRAM_RECEIVE == "telegram.receive"
    assert perms.TELEGRAM_REPLY == "telegram.reply"
