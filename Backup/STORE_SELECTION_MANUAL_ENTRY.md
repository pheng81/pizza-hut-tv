# Store Selection Flow - Manual Entry

## ✅ How It Works Now

### Flow:
```
1. Enter TV Code (4 digits)
   ↓
2. Enter Store ID (e.g., 1000, 1001, 1002)
   ↓
3. System fetches screens for THAT specific store
   ↓
4. Shows available screens for the store
   ↓
5. Select screen → Start playback
```

## 🏪 Why Manual Entry?

**Each store has different screens!**

Example:
- **Store 1000**: screen0, screen1, screen2, promo1
- **Store 1001**: screen0, promo1, promo2, promo3
- **Store 1002**: screen1, screen2, screen3

Users MUST specify which store they want to see screens for.

## 📋 Store ID Entry Screen

```
┌──────────────────────────────────────┐
│      Enter Store ID                  │
│                                      │
│      TV Code: 1234                   │
│                                      │
│  Store ID (e.g., 1000, 1001, 1002)  │
│  ┌────────────────────────────┐     │
│  │        1000                │     │
│  └────────────────────────────┘     │
│                                      │
│      [     Continue     ]            │
│                                      │
│  Each store has different screens    │
└──────────────────────────────────────┘
```

## ⚙️ API Call

```python
# Step 1: Fetch all data for TV code
url = f"https://everydayadvertise.com/api/stores_by_code/{tv_code}"
response = requests.get(url)

# Response structure:
{
  "success": true,
  "user": {"username": "username"},
  "stores": [
    {"id": "1000", "name": "Store 1000"},
    {"id": "1001", "name": "Store 1001"}
  ],
  "screens": {
    "1000": {
      "1000_screen0": {...},
      "1000_screen1": {...},
      "1000_promo1": {...}
    },
    "1001": {
      "1001_screen0": {...},
      "1001_promo1": {...}
    }
  }
}

# Step 2: Extract screens for specific store
screens_data = data['screens'][store_id]  # e.g., data['screens']['1000']
```

## ✅ Validation

### Valid Store ID:
```
Input: "1000"
✅ Store ID: 1000
→ Fetches screens for store 1000
→ Shows: screen0, screen1, promo1
```

### Invalid Store ID:
```
Input: "9999" (doesn't exist)
❌ Store '9999' not found.
   Available stores: 1000, 1001, 1002
```

### Empty Input:
```
Input: ""
❌ Please enter a store ID
```

### Non-numeric:
```
Input: "abc"
❌ Store ID must be numeric
```

## 🔧 Code Implementation

### Store ID Input:
```python
def select_store_by_input(self):
    store_id = self.input_field.get().strip()
    
    if not store_id:
        self.status_label.config(text="❌ Please enter a store ID")
        return
    
    if not store_id.isdigit():
        self.status_label.config(text="❌ Store ID must be numeric")
        return
    
    self.store_code = store_id
    print(f"✅ Store ID: {store_id}")
    self.show_screen_selection()
```

### Screen Fetching:
```python
def show_screen_selection(self):
    # Fetch data from API
    url = f"https://everydayadvertise.com/api/stores_by_code/{self.android_tv_code}"
    response = requests.get(url, timeout=10)
    data = response.json()
    
    # Get screens for specific store
    screens_data = data.get('screens', {}).get(self.store_code, {})
    
    if not screens_data:
        # Show available stores if store not found
        all_stores = data.get('stores', [])
        store_ids = [str(s.get('id')) for s in all_stores]
        status_label.config(
            text=f"❌ Store '{self.store_code}' not found.\n"
                 f"Available stores: {', '.join(store_ids)}"
        )
        return
    
    # Display screens...
```

## 🎯 Use Cases

### Case 1: Single Store Location
```
User at Store 1000
→ Enters TV Code: 1234
→ Enters Store ID: 1000
→ Sees screens for Store 1000 only
```

### Case 2: Multi-Store Setup
```
Admin managing multiple stores
→ Enters TV Code: 1234
→ Can enter different Store IDs:
   - 1000 → See Store 1000 screens
   - 1001 → See Store 1001 screens
   - 1002 → See Store 1002 screens
```

### Case 3: Wrong Store ID
```
User enters non-existent store
→ Enters TV Code: 1234
→ Enters Store ID: 9999
→ Error: "Store '9999' not found. Available: 1000, 1001, 1002"
→ User corrects to valid store ID
```

## 📊 Store vs Screen Relationship

```
TV CODE (1234)
    │
    ├── STORE 1000
    │   ├── screen0
    │   ├── screen1
    │   ├── screen2
    │   └── promo1
    │
    ├── STORE 1001
    │   ├── screen0
    │   ├── promo1
    │   └── promo2
    │
    └── STORE 1002
        ├── screen1
        ├── screen2
        └── screen3
```

## 🎬 Complete Flow Example

```
Step 1: TV Code Entry
┌────────────────────────┐
│ Enter TV Code          │
│ Input: 1234            │
│ [Continue]             │
└────────────────────────┘
         ↓
Step 2: Store ID Entry
┌────────────────────────┐
│ Enter Store ID         │
│ TV Code: 1234          │
│ Input: 1000            │
│ [Continue]             │
└────────────────────────┘
         ↓
Step 3: API Fetch
GET /api/stores_by_code/1234
→ Returns screens for all stores
         ↓
Step 4: Filter Screens
screens_data = data['screens']['1000']
→ Gets only Store 1000 screens
         ↓
Step 5: Display Screens
┌────────────────────────┐
│ Select Screen          │
│ TV Code: 1234          │
│ Store: 1000            │
│                        │
│ [🖥️ Screen0]          │
│ [🖥️ Screen1]          │
│ [🖥️ Screen2]          │
│ [📱 Promo1]           │
└────────────────────────┘
         ↓
Step 6: Start Playback
→ Fullscreen player for selected screen
```

## ✅ Benefits

1. **Store Isolation**: Each store sees only its screens
2. **Flexibility**: Admin can switch between stores easily
3. **Clear Errors**: Shows available stores if wrong ID entered
4. **Simple Input**: Just numeric store ID, no complex selection
5. **Fast**: Direct entry, no scrolling through store lists

## 🔍 Debugging

### Check Store ID:
```bash
# Player logs:
✅ Store ID: 1000
🔍 Loading available screens...
✅ Found 4 screen(s)
```

### Check API Response:
```bash
# If store not found:
❌ Store '1000' not found.
   Available stores: 1001, 1002, 1003
```

### Check Screen Count:
```bash
# Should show screen count for store:
✅ Found 4 screen(s)
# Means Store 1000 has 4 screens configured
```

## 📝 Summary

- **Manual Entry**: User types store ID directly
- **Why?**: Each store has different screens
- **Validation**: Checks if store exists, shows available stores if not
- **API Call**: Fetches all data, filters by store ID
- **Result**: Shows only screens for specified store

**Simple, clear, and works for multi-store setups!** ✨
