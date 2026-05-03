"""
DermaSense AI Backend API Tests
Tests all backend endpoints with realistic data
"""

import requests
import json
import sys

# Backend URL from frontend/.env
BACKEND_URL = "https://simple-html-build.preview.emergentagent.com/api"

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name}")
    print(f"{'='*70}")

def print_result(success, message):
    """Print test result"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {message}")

def test_root_endpoint():
    """Test GET /api/ - Root endpoint"""
    print_test_header("GET /api/ - Root Endpoint")
    
    try:
        response = requests.get(f"{BACKEND_URL}/", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if "message" in data:
                print_result(True, "Root endpoint returns welcome message")
                return True
            else:
                print_result(False, "Response missing 'message' field")
                return False
        else:
            print_result(False, f"Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Exception: {str(e)}")
        return False

def test_config_endpoint():
    """Test GET /api/config - Configuration status"""
    print_test_header("GET /api/config - Configuration Status")
    
    try:
        response = requests.get(f"{BACKEND_URL}/config", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            expected_keys = ["siliconflow", "openrouter", "amazon"]
            
            # Check all expected keys are present
            if all(key in data for key in expected_keys):
                # Check all values are boolean
                if all(isinstance(data[key], bool) for key in expected_keys):
                    # Since no API keys are set, all should be False
                    if all(data[key] == False for key in expected_keys):
                        print_result(True, "Config returns correct structure with all keys False (no API keys set)")
                        return True
                    else:
                        print_result(True, "Config returns correct structure (some API keys may be set)")
                        return True
                else:
                    print_result(False, "Config values are not boolean")
                    return False
            else:
                print_result(False, f"Missing expected keys. Got: {list(data.keys())}")
                return False
        else:
            print_result(False, f"Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Exception: {str(e)}")
        return False

def test_analyze_skin_endpoint():
    """Test POST /api/analyze-skin - Skin analysis with fallback"""
    print_test_header("POST /api/analyze-skin - Skin Analysis")
    
    # Realistic test data
    payload = {
        "skintype": "oily",
        "fitz": "III",
        "concerns": ["acne", "pigmentation"],
        "severity": "moderate",
        "sun": "Moderate",
        "sleep": 7,
        "stress": "moderate",
        "diet": "Balanced",
        "cleanser": "",
        "currentActives": [],
        "allergies": "",
        "pregnancy": "no",
        "image": None
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/analyze-skin",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response keys: {list(data.keys())}")
            
            # Expected keys in response
            expected_keys = [
                "skinType", "fitzpatrick", "primaryConcern", "severity",
                "uvRisk", "actives", "contraindications", "amRoutine",
                "pmRoutine", "incompatibilities", "productQueries"
            ]
            
            missing_keys = [key for key in expected_keys if key not in data]
            if missing_keys:
                print_result(False, f"Missing keys: {missing_keys}")
                return False
            
            # Validate actives array
            if not isinstance(data["actives"], list):
                print_result(False, "actives is not a list")
                return False
            
            if len(data["actives"]) < 1:
                print_result(False, "actives array is empty")
                return False
            
            print(f"Number of actives: {len(data['actives'])}")
            
            # Validate routines
            if not isinstance(data["amRoutine"], list) or len(data["amRoutine"]) < 1:
                print_result(False, "amRoutine is invalid or empty")
                return False
            
            if not isinstance(data["pmRoutine"], list) or len(data["pmRoutine"]) < 1:
                print_result(False, "pmRoutine is invalid or empty")
                return False
            
            print(f"AM Routine steps: {len(data['amRoutine'])}")
            print(f"PM Routine steps: {len(data['pmRoutine'])}")
            
            # Validate incompatibilities
            if not isinstance(data["incompatibilities"], list):
                print_result(False, "incompatibilities is not a list")
                return False
            
            # Validate productQueries
            if not isinstance(data["productQueries"], list):
                print_result(False, "productQueries is not a list")
                return False
            
            print(f"Product queries: {len(data['productQueries'])}")
            
            # Check if fallback was used
            if "_source" in data:
                print(f"Source: {data['_source']}")
                if data["_source"] == "fallback":
                    print_result(True, "Graceful fallback response (no API keys set)")
                else:
                    print_result(True, f"AI-powered response from {data['_source']}")
            else:
                print_result(True, "Valid response structure")
            
            return True
        else:
            print(f"Response: {response.text[:500]}")
            print_result(False, f"Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Exception: {str(e)}")
        return False

def test_products_search_endpoint():
    """Test POST /api/products-search - Product search"""
    print_test_header("POST /api/products-search - Product Search")
    
    payload = {
        "queries": ["The Ordinary Niacinamide", "CeraVe Moisturizer"]
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/products-search",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check response structure
            if "products" not in data:
                print_result(False, "Response missing 'products' key")
                return False
            
            if not isinstance(data["products"], list):
                print_result(False, "'products' is not a list")
                return False
            
            # Since no API key is set, should return empty list
            if len(data["products"]) == 0:
                print_result(True, "Returns empty products list (no Amazon API key set)")
                return True
            else:
                print(f"Found {len(data['products'])} products")
                print_result(True, "Product search working with API key")
                return True
        else:
            print_result(False, f"Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Exception: {str(e)}")
        return False

def test_products_search_empty_queries():
    """Test POST /api/products-search with empty queries"""
    print_test_header("POST /api/products-search - Empty Queries")
    
    payload = {"queries": []}
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/products-search",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("products") == []:
                print_result(True, "Empty queries return empty products list")
                return True
            else:
                print_result(False, f"Expected empty list, got: {data}")
                return False
        else:
            print_result(False, f"Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Exception: {str(e)}")
        return False

def run_all_tests():
    """Run all backend tests"""
    print("\n" + "="*70)
    print("DERMASENSE AI BACKEND API TESTS")
    print(f"Backend URL: {BACKEND_URL}")
    print("="*70)
    
    results = []
    
    # Run all tests
    results.append(("Root Endpoint", test_root_endpoint()))
    results.append(("Config Endpoint", test_config_endpoint()))
    results.append(("Analyze Skin", test_analyze_skin_endpoint()))
    results.append(("Products Search", test_products_search_endpoint()))
    results.append(("Products Search (Empty)", test_products_search_empty_queries()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
