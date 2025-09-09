# tldw_server Browser Extension Integration Plan v2.0

## Executive Summary
This document outlines a comprehensive plan to customize the page-assist browser extension to serve as a frontend for tldw_server. The plan addresses security, technical challenges, and provides a phased implementation approach prioritizing MVP features.

## Critical Considerations & Solutions

### 1. Security Architecture
**Challenges:**
- Secure storage of API keys and JWT tokens
- Cross-origin requests to local/remote servers
- Content Security Policy restrictions
- Preventing credential leakage

**Solutions:**
- Use browser's encrypted storage API (`chrome.storage.local` with encryption)
- Implement secure credential manager with memory-only sensitive data
- Add origin validation for all API requests
- Implement request signing for additional security
- Use manifest V3 service workers for better security isolation

### 2. CORS & Network Configuration
**Challenges:**
- Browser extensions face CORS restrictions
- Local server access from extension
- Mixed content (HTTP/HTTPS) issues
- WebSocket connections from extension context

**Solutions:**
- Server-side: Configure CORS headers specifically for extension origin
- Add `host_permissions` in manifest for server URLs
- Implement proxy pattern through background service worker
- Use `chrome.webRequest` API for header manipulation if needed
- Fallback to polling if WebSocket fails

### 3. Performance & Resource Management
**Challenges:**
- Browser extension memory limits (typically ~2GB)
- Storage quota restrictions
- Large file handling for media uploads
- State synchronization across tabs

**Solutions:**
- Implement streaming upload for large files
- Use IndexedDB for temporary file storage with cleanup
- Implement LRU cache for API responses
- Use Chrome's `offscreen` API for heavy processing
- Centralized state management in service worker

### 4. Error Handling & Recovery
**Challenges:**
- Network failures and timeouts
- Token expiration and refresh
- Server unavailability
- Rate limiting

**Solutions:**
- Exponential backoff retry strategy
- Automatic token refresh with queue for pending requests
- Offline mode with request queuing
- User-friendly error messages with recovery actions
- Health check endpoint monitoring

## Phase 1: Foundation & MVP (Weeks 1-3)

### 1.1 Project Setup
```bash
# Repository structure
tldw-browser-extension/
├── src/
│   ├── background/       # Service worker
│   ├── content/          # Content scripts
│   ├── popup/            # Extension popup
│   ├── options/          # Settings page
│   ├── sidebar/          # Main UI panel
│   ├── shared/           # Shared utilities
│   │   ├── api/          # API client
│   │   ├── auth/         # Auth management
│   │   ├── storage/      # Storage abstraction
│   │   └── types/        # TypeScript definitions
│   └── tests/            # Test suites
├── manifest.v3.json      # Chrome/Edge
└── manifest.v2.json      # Firefox
```

### 1.2 Core Authentication Module
**Single-User Mode:**
```typescript
interface SingleUserAuth {
  apiKey: string;
  serverUrl: string;
  validateConnection(): Promise<boolean>;
}
```

**Multi-User Mode:**
```typescript
interface MultiUserAuth {
  serverUrl: string;
  username: string;
  accessToken: string;
  refreshToken: string;
  tokenExpiry: number;
  autoRefresh(): void;
}
```

**Implementation:**
- Secure credential storage with encryption
- Auto-detection of auth mode from server
- Token refresh interceptor
- Session persistence across browser restarts

### 1.3 Basic API Client
```typescript
class TldwApiClient {
  constructor(config: TldwConfig);
  
  // Core methods
  chat(message: string, options?: ChatOptions): AsyncGenerator<ChatChunk>;
  search(query: string, options?: SearchOptions): Promise<SearchResults>;
  getServerInfo(): Promise<ServerInfo>;
  healthCheck(): Promise<boolean>;
}
```

### 1.4 Minimal UI Components
- **Sidebar Panel**: Chat interface with streaming responses
- **Settings Page**: Server URL, authentication, basic preferences
- **Status Indicator**: Connection status in toolbar icon

## Phase 2: Essential Features (Weeks 4-6)

### 2.1 Enhanced Chat Module
- Character selection dropdown
- Chat history management
- Context window configuration
- Provider/model selection
- Message editing and regeneration

### 2.2 RAG Search Integration
- Quick search bar in sidebar
- Search result display with snippets
- Filter by media type/date/tags
- Click-to-insert in chat context

### 2.3 Media Ingestion
- Right-click context menu for URLs
- "Send to tldw_server" option
- Progress notification for processing
- Quick webpage capture and summary

### 2.4 Error Recovery System
- Automatic reconnection logic
- Request retry queue
- User notification system
- Diagnostic information collection

## Phase 3: Advanced Features (Weeks 7-9)

### 3.1 Note-Taking System
- Quick note capture from selection
- Note organization with tags
- Search within notes
- Export capabilities

### 3.2 Prompt Management
- Prompt library browser
- Quick insertion toolbar
- Custom prompt creation
- Import/export prompts

### 3.3 Batch Operations
- Multiple URL processing
- Bulk media upload
- Queue management UI
- Background processing status

### 3.4 WebSocket Features
- Real-time transcription (if server supports)
- Live streaming responses
- Collaborative features (multi-user mode)

## Phase 4: Polish & Optimization (Weeks 10-12)

### 4.1 Performance Optimization
- Code splitting and lazy loading
- Request caching strategy
- Memory usage optimization
- Bundle size reduction

### 4.2 Advanced UI Features
- Keyboard shortcuts
- Custom themes
- Floating widget mode
- Multi-language support

### 4.3 Testing & QA
- Unit tests for all modules
- Integration tests with mock server
- End-to-end browser automation tests
- Performance benchmarking
- Security audit

### 4.4 Documentation
- User guide with screenshots
- API integration reference
- Troubleshooting guide
- Developer documentation

## Technical Implementation Details

### Manifest Configuration (V3)
```json
{
  "manifest_version": 3,
  "name": "tldw_server Assistant",
  "version": "1.0.0",
  "permissions": [
    "storage",
    "contextMenus",
    "activeTab",
    "notifications",
    "offscreen"
  ],
  "host_permissions": [
    "http://localhost:8000/*",
    "https://*/*"
  ],
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "action": {
    "default_popup": "popup.html",
    "default_icon": "icon.png"
  },
  "side_panel": {
    "default_path": "sidebar.html"
  },
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content.js"],
    "run_at": "document_idle"
  }],
  "content_security_policy": {
    "extension_pages": "script-src 'self'; object-src 'self'"
  }
}
```

### API Adapter Pattern
```typescript
// Abstract adapter interface
interface ApiAdapter {
  chat(request: ChatRequest): AsyncGenerator<ChatResponse>;
  search(query: SearchQuery): Promise<SearchResults>;
  ingestMedia(media: MediaInput): Promise<MediaResult>;
}

// tldw_server implementation
class TldwAdapter implements ApiAdapter {
  private client: TldwApiClient;
  
  async *chat(request: ChatRequest) {
    const stream = await this.client.post('/api/v1/chat/completions', {
      messages: request.messages,
      stream: true,
      model: request.model
    });
    
    for await (const chunk of stream) {
      yield this.transformResponse(chunk);
    }
  }
}
```

### State Management Architecture
```typescript
// Centralized state in service worker
class ExtensionState {
  private state: Map<string, any> = new Map();
  private listeners: Map<string, Set<Function>> = new Map();
  
  async get(key: string): Promise<any>;
  async set(key: string, value: any): Promise<void>;
  subscribe(key: string, callback: Function): void;
  unsubscribe(key: string, callback: Function): void;
}

// Message passing for state sync
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'STATE_UPDATE') {
    // Propagate state changes to all contexts
  }
});
```

### Security Measures
```typescript
// Credential encryption
class SecureStorage {
  private async encrypt(data: string): Promise<string> {
    const key = await this.getDerivedKey();
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv: this.getIV() },
      key,
      new TextEncoder().encode(data)
    );
    return btoa(String.fromCharCode(...new Uint8Array(encrypted)));
  }
  
  private async decrypt(data: string): Promise<string> {
    // Reverse of encryption
  }
}

// Request signing
class RequestSigner {
  sign(request: Request, apiKey: string): Request {
    const timestamp = Date.now();
    const signature = this.generateHMAC(request.url + timestamp, apiKey);
    request.headers.set('X-Signature', signature);
    request.headers.set('X-Timestamp', timestamp.toString());
    return request;
  }
}
```

## Development Milestones

### Milestone 1: Basic Connectivity (Week 2)
- [ ] Server connection established
- [ ] Authentication working (both modes)
- [ ] Simple chat request/response
- [ ] Error handling for common failures

### Milestone 2: Core Features (Week 4)
- [ ] Streaming chat responses
- [ ] RAG search integration
- [ ] Settings persistence
- [ ] Basic media ingestion

### Milestone 3: Enhanced UX (Week 6)
- [ ] Polished sidebar UI
- [ ] Context menu integration
- [ ] Keyboard shortcuts
- [ ] Progress indicators

### Milestone 4: Advanced Features (Week 9)
- [ ] Note-taking system
- [ ] Prompt management
- [ ] Batch operations
- [ ] WebSocket support

### Milestone 5: Production Ready (Week 12)
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Performance optimized
- [ ] Security audit passed

## Risk Mitigation

### Technical Risks
1. **WebSocket Compatibility**: Fallback to polling if WebSocket fails
2. **Large File Handling**: Implement chunked upload with resume capability
3. **Token Expiration**: Proactive refresh before expiration
4. **API Version Mismatch**: Version negotiation on connection

### User Experience Risks
1. **Complex Setup**: Provide setup wizard with auto-detection
2. **Performance Issues**: Progressive loading and lazy initialization
3. **Error Messages**: Clear, actionable error messages with solutions
4. **Feature Discovery**: Interactive tutorial on first launch

## Testing Strategy

### Unit Tests
- API client methods
- Authentication flows
- State management
- Utility functions

### Integration Tests
- Server communication
- Authentication scenarios
- Error recovery
- State synchronization

### E2E Tests
- Complete user workflows
- Multi-tab scenarios
- Extension installation/upgrade
- Permission handling

### Performance Tests
- Memory usage monitoring
- Request latency measurement
- Bundle size optimization
- Render performance

## Deployment Strategy

### Phase 1: Alpha Release
- Internal testing only
- Feature flags for experimental features
- Detailed logging for debugging
- Manual installation via developer mode

### Phase 2: Beta Release
- Limited user group
- Feedback collection system
- Automated error reporting
- Chrome Web Store unlisted

### Phase 3: Public Release
- Full feature set
- Polished UI/UX
- Complete documentation
- Published to Chrome Web Store and Firefox Add-ons

## Success Metrics

### Technical Metrics
- < 2 second connection time
- < 100ms chat response latency
- < 50MB memory footprint
- > 99% uptime for background service

### User Metrics
- > 80% successful setup completion
- < 5% error rate in normal operation
- > 90% feature utilization
- > 4.0 star rating in store

## Maintenance Plan

### Regular Updates
- Security patches within 24 hours
- Feature updates monthly
- Performance improvements quarterly
- Major version annually

### Support Structure
- GitHub issues for bug reports
- Discord/Forum for community support
- Documentation wiki
- Video tutorials

## Conclusion

This improved plan addresses the major challenges of integrating page-assist with tldw_server while maintaining security, performance, and user experience. The phased approach allows for iterative development with clear milestones and risk mitigation strategies. The emphasis on MVP features ensures a functional product early while building toward a comprehensive solution.