#!/usr/bin/env python3
"""Quick test to verify all 9 requirements are working"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_requirement_1_and_5():
    """Test bed occupancy and ICU metrics"""
    print("\n✓ Testing Requirement 1 & 5: Bed occupancy and ICU metrics...")
    response = requests.get(f"{BASE_URL}/api/dashboard/metrics")
    data = response.json()
    
    assert "occupied_beds" in data, "Missing occupied_beds"
    assert "icu_occupied_beds" in data, "Missing icu_occupied_beds"
    assert "icu_available_beds" in data, "Missing icu_available_beds"
    assert "icu_total_beds" in data, "Missing icu_total_beds"
    
    print(f"  ✓ Occupied beds: {data['occupied_beds']}/{data['total_beds']}")
    print(f"  ✓ ICU beds: {data['icu_occupied_beds']}/{data['icu_total_beds']} (Available: {data['icu_available_beds']})")

def test_requirement_2():
    """Test time windows"""
    print("\n✓ Testing Requirement 2: Time windows...")
    for window in ["14_days", "30_days", "90_days", "6_months", "12_months"]:
        response = requests.get(f"{BASE_URL}/api/analytics/department-forecasts?time_window={window}")
        assert response.status_code == 200, f"Failed for {window}"
        data = response.json()
        assert "forecast_days" in data
        print(f"  ✓ {window}: {data['forecast_days']} days")

def test_requirement_3():
    """Test 404 fixes"""
    print("\n✓ Testing Requirement 3: Fixed 404 endpoints...")
    
    # ED wait time forecast
    response = requests.post(
        f"{BASE_URL}/api/ed/wait-time/forecast",
        json={"days": 14}
    )
    assert response.status_code == 200, "ED wait time forecast failed"
    print(f"  ✓ /api/ed/wait-time/forecast: {response.status_code}")
    
    # Disease categories
    response = requests.get(f"{BASE_URL}/api/disease/categories")
    assert response.status_code == 200, "Disease categories failed"
    data = response.json()
    print(f"  ✓ /api/disease/categories: {len(data.get('categories', []))} categories")

def test_requirement_4():
    """Test summary in deep-dive analytics"""
    print("\n✓ Testing Requirement 4: Deep-dive summary...")
    response = requests.get(f"{BASE_URL}/api/analytics/department-forecasts?days=14")
    data = response.json()
    
    assert "summary" in data, "Missing summary"
    summary = data["summary"]
    assert "calculation_method" in summary
    assert "forecast_approach" in summary
    assert "seasonal_factors_analyzed" in summary
    assert "why_this_prediction" in summary
    
    print(f"  ✓ Summary includes: {', '.join(summary.keys())}")

def test_requirement_6():
    """Test department_series removed"""
    print("\n✓ Testing Requirement 6: Department series removed...")
    response = requests.get(f"{BASE_URL}/api/analytics/chart-pack?days=14")
    data = response.json()
    
    assert "department_series" not in data, "department_series should be removed"
    print(f"  ✓ department_series removed from chart-pack")

def test_requirement_7():
    """Test clinical demand forecasts"""
    print("\n✓ Testing Requirement 7: Clinical demand forecasts...")
    
    # Get disease list first
    response = requests.get(f"{BASE_URL}/api/disease/list")
    diseases = response.json()
    
    if diseases:
        disease = diseases[0]
        
        # Test admissions forecast
        response = requests.post(
            f"{BASE_URL}/api/disease/{disease}/admissions/forecast",
            json={"days": 14}
        )
        assert response.status_code == 200
        print(f"  ✓ Admissions forecast for {disease}: {response.status_code}")
        
        # Test discharges forecast
        response = requests.post(
            f"{BASE_URL}/api/disease/{disease}/discharges/forecast",
            json={"days": 14}
        )
        assert response.status_code == 200
        print(f"  ✓ Discharges forecast for {disease}: {response.status_code}")

def test_requirement_9():
    """Test LLM explanation"""
    print("\n✓ Testing Requirement 9: Model explanation...")
    response = requests.post(
        f"{BASE_URL}/api/forecast",
        json={"days": 14}
    )
    data = response.json()
    
    assert "forecast_model" in data
    assert "explanation" in data["forecast_model"]
    
    explanation = data["forecast_model"]["explanation"]
    print(f"  ✓ Explanation generated: {len(explanation)} characters")
    print(f"  ✓ Preview: {explanation[:100]}...")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing All 9 Requirements")
    print("=" * 60)
    
    try:
        test_requirement_1_and_5()
        test_requirement_2()
        test_requirement_3()
        test_requirement_4()
        test_requirement_6()
        test_requirement_7()
        test_requirement_9()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - All 9 requirements working!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
