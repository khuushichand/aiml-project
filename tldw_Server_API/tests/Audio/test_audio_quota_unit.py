import pytest


@pytest.mark.asyncio
async def test_user_tier_default_and_set_roundtrip():
    from tldw_Server_API.app.core.Usage.audio_quota import get_user_tier, set_user_tier
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

    uid = 777777
    pool = await get_db_pool()
    # Ensure deterministic state for this uid
    await set_user_tier(uid, "free")
    await pool.execute("DELETE FROM audio_user_tiers WHERE user_id = ?", uid)

    # default is free when no row exists
    assert (await get_user_tier(uid)) == "free"
    await set_user_tier(uid, "premium")
    assert (await get_user_tier(uid)) == "premium"
