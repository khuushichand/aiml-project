import pytest
import asyncio

from tldw_Server_API.app.core.TTS.tts_resource_manager import get_resource_manager, close_resource_manager


@pytest.mark.asyncio
async def test_http_client_pool_reuse_and_stats():
    mgr = await get_resource_manager({
        "max_http_connections": 5,
        "max_keepalive_connections": 3,
        "keepalive_expiry": 5.0,
        "connection_timeout": 1.0,
    })

    # Acquire clients for two providers
    c1 = await mgr.get_http_client('openai', base_url='https://api.openai.com')
    c2 = await mgr.get_http_client('elevenlabs', base_url='https://api.elevenlabs.io')
    c1b = await mgr.get_http_client('openai', base_url='https://api.openai.com')

    # Should reuse client for same provider
    assert c1 is c1b

    stats = mgr.connection_pool.get_stats()
    assert 'openai' in stats and 'elevenlabs' in stats
    assert stats['openai']['use_count'] >= 2

    # Cleanup
    await mgr.connection_pool.close_all()


@pytest.mark.asyncio
async def test_streaming_session_lifecycle_and_cleanup():
    mgr = await get_resource_manager()

    # Create and close sessions
    sid1 = await mgr.create_streaming_session('openai')
    sid2 = await mgr.create_streaming_session('openai')

    # Ensure sessions exist
    stats = mgr.get_statistics()
    assert stats['sessions']['active'] >= 2
    assert sid1 in stats['sessions']['ids'] and sid2 in stats['sessions']['ids']

    # Close one session
    await mgr.session_manager.close_session(sid1)
    stats2 = mgr.get_statistics()
    assert sid1 not in stats2['sessions']['ids']

    # Close remaining and cleanup all
    await mgr.session_manager.close_session(sid2)
    await mgr.cleanup_all()
    stats3 = mgr.get_statistics()
    assert stats3['sessions']['active'] == 0

    # Shutdown manager
    await close_resource_manager()
