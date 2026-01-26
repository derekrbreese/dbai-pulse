# Decisions - Draft & Yahoo Integration

## 2026-01-26: Architecture Decisions

### D1: Use Fantasy Football Calculator as Primary ADP Source
**Decision**: Use FFC's free REST API rather than computing from Sleeper drafts
**Rationale**: 
- No auth required, simple JSON response
- Already aggregated data (vs computing ourselves)
- Sleeper draft data can be fallback/supplementary

### D2: Use YFPY for Yahoo Integration
**Decision**: Use the `yfpy` library instead of raw Yahoo API calls
**Rationale**:
- Handles OAuth token refresh automatically
- Provides Python object models for all data types
- Well-maintained (199 commits, active development)
**Risk**: GPL-3.0 license - need to review compatibility

### D3: Player ID Mapping Strategy
**Decision**: Build a mapping service using player name + team matching
**Rationale**:
- Yahoo uses different player IDs than Sleeper
- Names/teams are common identifiers
- Cache mappings to avoid repeated lookups

### D4: Phase Implementation Order
**Decision**: MVP = ADP data + Yahoo roster sync (skip live draft assistant initially)
**Rationale**:
- Draft data adds immediate value to player cards
- Roster sync is core user need
- Live draft features are complex and lower priority
