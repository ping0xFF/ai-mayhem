# Real APIs - Provider Analysis & Implementation

This directory contains production-ready API integrations for blockchain data providers.

## 🏆 **Provider Comparison Summary**

| Provider | Response Size | Transactions | Speed | Support | Status |
|----------|---------------|--------------|-------|---------|--------|
| **Alchemy** | ~509 bytes/txn | 1000 max | Fast | Base ✅ | **Winner** |
| **Covalent** | ~7.3KB/txn | 100/page | Medium | Multi-chain | Fallback |
| **Bitquery** | Variable | Unlimited | Slow | Multi-chain | Fallback |

## 🚀 **Alchemy - Primary Provider**

### **File**: `alchemy_provider.py` 

**📝 Naming Note**: This file is named `alchemy_provider.py` (not `alchemy.py`) to avoid naming conflicts with the official Alchemy SDK package.

**Why Alchemy Won:**
- ✅ **Optimal Response Size**: ~509 bytes per transaction
- ✅ **Real Data**: Recent Base network transactions with full details
- ✅ **Time Filtering**: Block-based time range queries
- ✅ **Pagination**: `maxCount` (1000) + `pageKey` for large histories
- ✅ **TDD Implementation**: 17 comprehensive tests (unit + integration)
- ✅ **Production Ready**: Full error handling and fallback mechanisms

### **Technical Implementation**

**Dual Network Approach:**
- **Base Mainnet**: Direct HTTP requests using `aiohttp` (Python SDK doesn't support Base yet)
- **Other Networks**: Official `alchemy-sdk` for supported networks

**Key Function:**
```python
async def fetch_wallet_activity_alchemy_live(
    address: str,
    max_transactions: int = 1000,
    hours_back: Optional[int] = None,
    network: str = "base-mainnet"
) -> Dict[str, Any]
```

**Dependencies:**
- `alchemy-sdk` - Official Alchemy Python SDK
- `aiohttp>=3.8.0` - For direct Base mainnet HTTP requests
- `dataclass-wizard` - Required dependency for alchemy-sdk

### **Test Coverage**

**File**: `test_alchemy.py` - 17 test cases total

**Unit Tests (Mocked):**
- Provider initialization and configuration
- Transaction classification logic
- Value extraction and token symbol handling
- Error handling for API failures
- Time filtering with block calculations

**Integration Tests (Real API):**
- Live Base chain API calls with real data
- Time filtering validation with recent transactions
- Response size and format verification
- Network connection and authentication testing

**Test Command:**
```bash
cd real_apis
python -m unittest test_alchemy.py -v
```

### **Configuration**

```bash
# .env file
ALCHEMY_API_KEY=your_alchemy_api_key_here
WALLET_RECON_SOURCE=alchemy  # Enable Alchemy as primary
```

### **Usage Examples**

```python
from real_apis.alchemy_provider import fetch_wallet_activity_alchemy_live

# Fetch recent Base chain transactions
result = await fetch_wallet_activity_alchemy_live(
    address="0x742d35Cc6e5F18B5c8a3B3d88A7B14BeB8b5Ec",
    max_transactions=1000,
    hours_back=24,
    network="base-mainnet"
)

print(f"Found {len(result['events'])} transactions")
print(f"Network: {result['metadata']['network']}")
print(f"Source: {result['metadata']['source']}")
```

## 📡 **Covalent - Secondary Provider**

### **File**: `covalent.py`

**Size Optimization Achievement: 89x Reduction**
- **Problem**: Regular endpoints returned 16MB+ responses
- **Solution**: Page-based endpoints (`/transactions_v3/page/0/`)
- **Result**: 735KB for 100 transactions (~7.3KB per transaction)

### **Critical Warnings**
- ❌ **NEVER use `/transactions_v3/`** - returns 16MB+ responses
- ✅ **ALWAYS use `/transactions_v3/page/{N}/`** - provides 89x size reduction
- ❌ **NEVER use `/transactions_v2/`** - even worse at 28MB+ responses

### **Endpoint Testing Results**

| Endpoint | Size | Transactions | Avg/Txn | Status | Notes |
|----------|------|-------------|---------|--------|-------|
| **Page-based** | 735KB | 100 | ~7.3KB | ✅ **WINNER** | 89x reduction |
| **Regular v3** | 16MB | 25 | ~650KB | ❌ Avoid | Massive bloat |
| **v2** | 28.7MB | N/A | N/A | ❌ Avoid | Even larger |
| **Transfers** | 107B | N/A | N/A | ❌ Error | Requires contract |
| **Summary** | 817B | N/A | N/A | ⚠️ Limited | Metadata only |

### **Optimized curl Commands**

```bash
# ✅ GOOD: Page-based endpoint (89x size reduction)
curl -X GET \
  "https://api.covalenthq.com/v1/base-mainnet/address/$WALLET_ADDRESS/transactions_v3/page/0/" \
  -H "Authorization: Bearer $COVALENT_API_KEY" \
  -H "Content-Type: application/json"

# ❌ BAD: Regular endpoint (16MB+ responses)
curl -X GET \
  "https://api.covalenthq.com/v1/base-mainnet/address/$WALLET_ADDRESS/transactions_v3/" \
  -H "Authorization: Bearer $COVALENT_API_KEY" \
  -H "Content-Type: application/json"
```

## 🔍 **Bitquery - Fallback Provider**

### **File**: `bitquery.py`

**When to Use:**
- Detailed transaction analysis beyond Alchemy/Covalent capabilities
- Multi-chain queries requiring GraphQL flexibility
- When both Alchemy and Covalent are unavailable

**Characteristics:**
- GraphQL-based queries for maximum flexibility
- Offset-based pagination with deduplication
- More detailed transaction data but slower responses
- Comprehensive error handling and logging

## 🔄 **Fallback Chain**

The system automatically falls back through providers:

```
Alchemy (Base chain) → Covalent (multi-chain) → Bitquery (GraphQL) → Mock Data
```

**Configuration:**
```bash
# Primary provider
WALLET_RECON_SOURCE=alchemy
ALCHEMY_API_KEY=your_key

# Fallback providers (optional)
COVALENT_API_KEY=your_key
BITQUERY_ACCESS_TOKEN=your_key
```

## 📊 **Performance Comparison**

### **Response Size (per transaction)**
- **Alchemy**: ~509 bytes ⭐
- **Covalent**: ~7.3KB (14x larger than Alchemy)
- **Bitquery**: Variable (depends on query complexity)

### **Maximum Transactions per Request**
- **Alchemy**: 1000 transactions
- **Covalent**: 100 transactions (paginated)
- **Bitquery**: Unlimited (with pagination)

### **Time Filtering**
- **Alchemy**: Block-based filtering (`fromBlock`)
- **Covalent**: Limited time filtering
- **Bitquery**: Flexible GraphQL time queries

## 🧪 **Testing All Providers**

```bash
# Test Alchemy (primary)
cd real_apis
python -m unittest test_alchemy.py -v

# Test Covalent integration
python demos/covalent_demo.py

# Test with live APIs (all providers)
python demos/wallet_recon_live.py
```

## 📚 **Documentation References**

- **Alchemy API**: https://docs.alchemy.com/
- **Alchemy SDK**: https://github.com/alchemyplatform/alchemy-sdk-py
- **Covalent OpenAPI**: https://api.covalenthq.com/v1/openapiv3/
- **Covalent Docs**: https://goldrush.dev/docs/api-reference/
- **Bitquery**: https://docs.bitquery.io/

## 🛠️ **Development Notes**

### **Adding New Providers**
1. Create provider file in `real_apis/`
2. Implement standardized interface matching existing providers
3. Add comprehensive test coverage (unit + integration)
4. Update fallback chain in `mock_tools.py`
5. Document in this README

### **Provider Interface Standards**
All providers should implement:
- Async function signature: `fetch_wallet_activity_*_live(address, max_transactions, hours_back, network)`
- Standard response format with `events` and `metadata`
- Error handling with graceful fallback
- Response size tracking for monitoring
- Provenance tracking for data lineage

---

**Status**: Production ready with comprehensive test coverage and documentation.