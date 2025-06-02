#!/usr/bin/env python3
"""
🧪 TEST RUNNER FOR PDF+WEB SEARCH SYSTEM

Simple test runner that can execute different test categories.

Usage:
    python run_tests.py                    # Run basic tests
    python run_tests.py --full             # Run comprehensive suite
    python run_tests.py --overflow         # Run token overflow scenarios
    python run_tests.py --pdf              # Test PDF processing only
    python run_tests.py --web              # Test web search only
    python run_tests.py --csv              # Test CSV processing only
    python run_tests.py --quick            # Quick smoke test
"""

import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_environment():
    """Check if environment is ready for testing"""
    issues = []
    
    # Check API keys
    if not os.environ.get("ANTHROPIC_API_KEY"):
        issues.append("❌ ANTHROPIC_API_KEY missing")
    else:
        print("✅ Anthropic API key found")
        
    if not os.environ.get("OPENAI_API_KEY"):
        issues.append("⚠️  OPENAI_API_KEY missing (OpenAI tests will be skipped)")
    else:
        print("✅ OpenAI API key found")
        
    if not os.environ.get("GOOGLE_API_KEY"):
        issues.append("⚠️  GOOGLE_API_KEY missing (Google tests will be skipped)")
    else:
        print("✅ Google API key found")
    
    # Check test files
    test_files = [
        "Q17 materials pt 1.pdf",
        "Q17 materials pt 2.pdf",
        "files/2016_Special_TheARCandTheCovenants2/the-arc-and-the-covenants-2.pdf"
    ]
    
    available_files = []
    for file_path in test_files:
        if Path(file_path).exists():
            available_files.append(file_path)
            print(f"✅ Found test file: {file_path}")
        else:
            print(f"⚠️  Missing test file: {file_path}")
    
    if not available_files:
        issues.append("❌ No test PDF files found")
    
    return issues

def run_quick_test():
    """Run a quick smoke test"""
    print("🚀 RUNNING QUICK SMOKE TEST")
    print("=" * 40)
    
    try:
        # Test basic imports
        print("📦 Testing imports...")
        from models_anthropic import anthropic_ask_with_files
        from anthropic_token_manager import AnthropicTokenManager
        import anthropic
        print("   ✅ All imports successful")
        
        # Test API connection
        print("🔗 Testing API connection...")
        client = anthropic.Anthropic()
        
        # Simple test call
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'test'"}]
        )
        print(f"   ✅ API connection successful: '{response.content[0].text.strip()}'")
        
        # Test token counting
        print("🪙 Testing token counting...")
        token_response = client.messages.count_tokens(
            model="claude-3-5-haiku-20241022",
            messages=[{"role": "user", "content": "Test message"}]
        )
        print(f"   ✅ Token counting works: {token_response.input_tokens} tokens")
        
        print("\n✅ QUICK TEST PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ QUICK TEST FAILED: {e}")
        return False

def run_pdf_tests():
    """Run PDF processing tests"""
    print("🧪 RUNNING PDF PROCESSING TESTS")
    print("=" * 40)
    
    # Find available PDFs
    test_pdfs = []
    pdf_candidates = [
        "Q17 materials pt 1.pdf",
        "Q17 materials pt 2.pdf", 
        "files/2016_Special_TheARCandTheCovenants2/the-arc-and-the-covenants-2.pdf",
        "files/2018_Energy_PascalsWager/pascals-wager-2018.pdf"
    ]
    
    for pdf_path in pdf_candidates:
        if Path(pdf_path).exists():
            test_pdfs.append(Path(pdf_path))
            
    if not test_pdfs:
        print("❌ No PDF files found for testing")
        return False
    
    print(f"📄 Found {len(test_pdfs)} PDF(s) to test")
    
    success_count = 0
    
    for pdf_path in test_pdfs[:2]:  # Test first 2 PDFs to avoid token overuse
        print(f"\n🔬 Testing: {pdf_path.name}")
        
        try:
            from anthropic_token_manager import AnthropicTokenManager
            import anthropic
            
            client = anthropic.Anthropic()
            token_manager = AnthropicTokenManager("claude-3-5-haiku-20241022", client, Path.cwd())
            
            # Analyze file
            file_info = token_manager.analyze_files([pdf_path])
            if file_info:
                info = file_info[0]
                print(f"   📊 {info.estimated_tokens:,} tokens, {info.total_pages} pages")
                print(f"   🎯 Can fit full: {info.can_fit_full}")
                
                # Test planning
                simple_query = "What is the main topic of this document?"
                plan = token_manager.plan_request([pdf_path], simple_query, False)
                print(f"   📋 Strategy: {plan.strategy}")
                print(f"   🪙 Estimated total: {plan.estimated_total_tokens:,}")
                
                success_count += 1
            else:
                print("   ❌ Failed to analyze file")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    success_rate = success_count / len(test_pdfs[:2]) * 100
    print(f"\n📊 PDF Test Results: {success_count}/{len(test_pdfs[:2])} passed ({success_rate:.0f}%)")
    
    return success_count > 0

def run_web_tests():
    """Run web search tests"""
    print("🧪 RUNNING WEB SEARCH TESTS")
    print("=" * 40)
    
    test_queries = [
        "What is the current price of Bitcoin?",
        "What happened in the stock market today?"
    ]
    
    success_count = 0
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🔬 Web Test {i}: {query}")
        
        try:
            from models_anthropic import anthropic_ask_with_files
            
            start_time = time.time()
            answer, input_tokens, cached_tokens, output_tokens, thinking_tokens, web_used, web_sources = anthropic_ask_with_files(
                file_paths=[],
                prompt_text=query,
                model_name="claude-3-5-haiku-20241022",
                web_search=True
            )
            
            duration = time.time() - start_time
            total_tokens = input_tokens + output_tokens
            
            print(f"   ✅ Success in {duration:.1f}s")
            print(f"   🌐 Web search used: {web_used}")
            print(f"   🪙 Tokens: {total_tokens:,}")
            print(f"   📝 Answer length: {len(answer)} chars")
            
            if not web_used:
                print("   ⚠️  Warning: Web search was not triggered")
            
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
    
    success_rate = success_count / len(test_queries) * 100
    print(f"\n📊 Web Test Results: {success_count}/{len(test_queries)} passed ({success_rate:.0f}%)")
    
    return success_count > 0

def run_csv_tests():
    """Run CSV processing tests"""
    print("🧪 RUNNING CSV PROCESSING TESTS")
    print("=" * 40)
    
    # Look for Excel files to convert to CSV
    excel_files = [
        "Q4 materials pt 2.xlsx",
        "Q4 materials pt 3.xlsx"
    ]
    
    available_files = [Path(f) for f in excel_files if Path(f).exists()]
    
    if not available_files:
        print("❌ No Excel/CSV files found for testing")
        return False
    
    print(f"📊 Found {len(available_files)} Excel file(s) to test")
    
    success_count = 0
    
    for excel_path in available_files[:1]:  # Test first file only
        print(f"\n🔬 Testing: {excel_path.name}")
        
        try:
            import pandas as pd
            
            # Read Excel file
            df = pd.read_excel(excel_path)
            print(f"   📊 {len(df)} rows, {len(df.columns)} columns")
            
            # Convert to CSV temporarily
            csv_path = excel_path.with_suffix('.csv')
            df.to_csv(csv_path, index=False)
            print(f"   💾 Converted to CSV: {csv_path.name}")
            
            # Test CSV parsing if available
            try:
                from file_store import parse_csv_to_markdown_format, estimate_markdown_tokens
                
                csv_data = parse_csv_to_markdown_format(csv_path, max_rows=10)
                estimated_tokens = estimate_markdown_tokens(csv_data['markdown_data'])
                
                print(f"   📝 Markdown conversion: {csv_data['total_rows']} total rows")
                print(f"   🪙 Estimated tokens: {estimated_tokens:,}")
                
                success_count += 1
                
            except Exception as e:
                print(f"   ⚠️  CSV parsing failed: {e}")
            
            # Clean up temp CSV
            if csv_path.exists():
                csv_path.unlink()
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    success_rate = success_count / len(available_files[:1]) * 100
    print(f"\n📊 CSV Test Results: {success_count}/{len(available_files[:1])} passed ({success_rate:.0f}%)")
    
    return success_count > 0

def main():
    """Main test runner"""
    print("🧪 PDF+WEB SEARCH SYSTEM TEST RUNNER")
    print("=" * 50)
    
    # Parse command line arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    if "--help" in args or "-h" in args:
        print(__doc__)
        return
    
    # Check environment
    print("🔧 ENVIRONMENT CHECK")
    print("-" * 20)
    issues = check_environment()
    
    if issues:
        print("\n⚠️  ENVIRONMENT ISSUES:")
        for issue in issues:
            print(f"   {issue}")
        
        critical_issues = [i for i in issues if i.startswith("❌")]
        if critical_issues:
            print("\n❌ Cannot proceed due to critical issues")
            return
    
    print("\n✅ Environment check passed")
    
    # Determine which tests to run
    run_full = "--full" in args
    run_overflow = "--overflow" in args
    run_pdf_only = "--pdf" in args
    run_web_only = "--web" in args
    run_csv_only = "--csv" in args
    run_quick_only = "--quick" in args
    
    # Run tests based on arguments
    if run_quick_only:
        run_quick_test()
        
    elif run_full:
        print("\n🚀 RUNNING COMPREHENSIVE TEST SUITE")
        try:
            from integration_test_suite import IntegrationTestSuite
            suite = IntegrationTestSuite()
            suite.run_all_tests()
        except ImportError:
            print("❌ Comprehensive test suite not available")
            
    elif run_overflow:
        print("\n🚨 RUNNING TOKEN OVERFLOW SCENARIOS")
        try:
            from test_token_overflow_scenarios import TokenOverflowTester
            tester = TokenOverflowTester()
            tester.run_all_scenarios()
        except ImportError:
            print("❌ Token overflow tester not available")
            
    elif run_pdf_only:
        run_pdf_tests()
        
    elif run_web_only:
        run_web_tests()
        
    elif run_csv_only:
        run_csv_tests()
        
    else:
        # Default: run basic tests
        print("\n🚀 RUNNING BASIC TESTS")
        print("(Use --help to see all options)")
        
        all_passed = True
        
        if not run_quick_test():
            all_passed = False
            
        if not run_pdf_tests():
            all_passed = False
            
        if not run_web_tests():
            all_passed = False
            
        print(f"\n🎯 BASIC TESTS {'PASSED' if all_passed else 'FAILED'}")
        
        if not all_passed:
            print("💡 Try running individual test categories to isolate issues:")
            print("   python run_tests.py --pdf")
            print("   python run_tests.py --web")
            print("   python run_tests.py --quick")

if __name__ == "__main__":
    main()