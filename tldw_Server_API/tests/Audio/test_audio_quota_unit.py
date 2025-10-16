import pytest


@pytest.mark.asyncio
async def test_user_tier_default_and_set_roundtrip():
    from tldw_Server_API.app.core.Usage.audio_quota import get_user_tier
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

    uid = 777777
    pool = await get_db_pool()
    # ensure table and clear any existing row for this uid to make test deterministic
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_user_tiers (
            user_id INTEGER PRIMARY KEY,
            tier TEXT NOT NULL
        );
        """
    )
    await pool.execute("DELETE FROM audio_user_tiers WHERE user_id = ?", uid)

    # default is free
    assert (await get_user_tier(uid)) == "free"
    await pool.execute(
        "INSERT INTO audio_user_tiers (user_id, tier) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET tier=excluded.tier",
        uid, "premium",
    )
    assert (await get_user_tier(uid)) == "premium"
