# AI Mayhem Data Flow Architecture

## Overview

This document describes the three-layer data model used by the AI Mayhem agent system for blockchain data monitoring and analysis. The architecture ensures data provenance, prevents state sprawl, and enables efficient querying across different data granularities.

## Three-Layer Architecture

### Layer 1: Scratch JSON Cache (Raw Data)
**Purpose**: Store raw API/MCP responses without schema commitment
- **Retention**: 7 days (short-lived, purgeable)
- **Usage**: Always written first by Worker node
- **Fields**:
  - `id` (primary key): Deterministic identifier
  - `source`: Data source (e.g., "nansen", "mock_tools")
  - `timestamp`: When data was fetched
  - `raw_json`: Original API response
  - `provenance`: Source metadata and snapshot information

### Layer 2: Normalized Events (Structured Data)
**Purpose**: Curated schema for recurring entities
- **Retention**: 30 days (mid-term)
- **Usage**: Written by Analyze node after parsing Layer 1 data
- **Fields**:
  - `event_id` (primary key): Deterministic hash of transaction details
  - `wallet`: Wallet address (if applicable)
  - `event_type`: "swap", "lp_add", "lp_remove", "metrics"
  - `pool`: Pool identifier (if applicable)
  - `value`: Event-specific structured data
  - `timestamp`: Unix timestamp
  - `source_id`: References Layer 1 record
  - `chain`: Blockchain (default: "base")

### Layer 3: Artifacts/Briefs (Human-Readable)
**Purpose**: Human-readable summaries and computed signals
- **Retention**: 90 days (long-term)
- **Usage**: Written by Brief node, persisted by Memory node
- **Fields**:
  - `artifact_id` (primary key): Deterministic identifier
  - `timestamp`: When brief was generated
  - `summary_text`: Human-readable summary
  - `signals`: Computed metrics and indicators
  - `next_watchlist`: Suggested items to monitor
  - `source_ids`: References to Layer 1 records
  - `event_count`: Number of events processed

## Data Flow Diagram

```
[ Layer 1: Scratch JSON Cache ]            (short-lived, 7d)
  id (pk) ── source ── timestamp ── raw_json ── provenance
      │
      │  (normalize)
      ▼
[ Layer 2: Normalized Events ]             (30d)
  event_id (pk) ─ wallet ─ event_type ─ pool ─ value ─ ts ─ source_id ─ chain
      │
      │  (aggregate + compute signals)
      ▼
[ Layer 3: Artifacts / Briefs ]            (90d)
  artifact_id (pk) ─ ts ─ summary_text ─ signals ─ next_watchlist ─ source_ids ─ event_count

Provenance chain:
Artifacts.source_ids → Events.event_id → Scratch.id
```

## Flow Example

1. **Worker Node** fetches wallet activity from Nansen API
2. **Raw response** saved to Layer 1 with provenance metadata
3. **Analyze Node** parses raw data and creates normalized events in Layer 2
4. **Brief Node** aggregates events and computes signals for Layer 3
5. **Memory Node** persists final artifacts and updates cursors

## Provenance Tracking

Every artifact in Layer 3 maintains full traceability back to original source data:

- **Brief** → Contains `source_ids` pointing to Layer 1 records
- **Events** → Reference their originating `source_id` from Layer 1
- **Raw Data** → Original API responses with full metadata

This enables:
- **Audit trails**: Complete history of data transformations
- **Debugging**: Easy tracing of issues back to source data
- **Compliance**: Full data lineage for regulatory requirements

## Node Responsibilities

- **Planner Node**: Decides what data to fetch based on cursor staleness
- **Worker Node**: Executes API calls, saves raw data (Layer 1)
- **Analyze Node**: Normalizes events (Layer 2), computes signals
- **Brief Node**: Creates summaries (Layer 3) based on thresholds
- **Memory Node**: Persists artifacts, updates cursors for next run

## Data Retention Strategy

- **Layer 1**: 7 days - Raw responses can be purged after normalization
- **Layer 2**: 30 days - Event data retained for trend analysis
- **Layer 3**: 90 days - Human-readable artifacts kept long-term

## Benefits

1. **Schema Flexibility**: Layer 1 accepts any JSON without schema constraints
2. **Performance**: Efficient querying at appropriate granularity levels
3. **Debugging**: Full provenance chain for troubleshooting
4. **Scalability**: Each layer optimized for its specific use case
5. **Data Integrity**: Idempotent operations prevent duplicates
