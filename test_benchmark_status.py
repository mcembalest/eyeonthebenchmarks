import unittest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sqlite3
import os
import json

class TestBenchmarkStatus(unittest.TestCase):
    def setUp(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--remote-debugging-port=9222')
        self.driver = webdriver.Chrome(options=options)
        self.driver.get('file:///Users/maxcembalest/Desktop/repos/eyeonthebenchmarks/src/renderer/index.html')
        self.db_path = os.path.join(os.path.dirname(__file__), 'benchmarks.db')
        
    def tearDown(self):
        self.driver.quit()
        
    def test_benchmark_status_flow(self):
        """Test that benchmark status properly transitions from in-progress to complete
        and persists after page refresh"""
        
        # 1. Create a simple benchmark
        test_benchmark = {
            "name": "Status Test Benchmark",
            "description": "Testing status transitions",
            "prompts": [{
                "prompt": "What is 2+2?",
                "expected": "4"
            }],
            "models": ["gpt-3.5-turbo"]
        }
        
        # Click new benchmark button
        new_btn = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, 'newBenchmarkBtn'))
        )
        new_btn.click()
        
        # Fill in benchmark details
        name_input = self.driver.find_element(By.ID, 'benchmarkNameInput')
        name_input.send_keys(test_benchmark['name'])
        
        description_input = self.driver.find_element(By.ID, 'benchmarkDescriptionInput')
        description_input.send_keys(test_benchmark['description'])
        
        # First wait for any existing alerts and dismiss them
        try:
            alert = WebDriverWait(self.driver, 2).until(EC.alert_is_present())
            alert.accept()
        except:
            pass  # No alert present
            
        # Add prompt
        # First find the prompts table and wait for it to be populated
        prompts_table = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'promptsTable'))
        )
        
        # Click Add Row button
        add_row_btn = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[text()='Add Row']"))
        )
        add_row_btn.click()
        
        # Get the first row's cells
        tbody = prompts_table.find_element(By.TAG_NAME, 'tbody')
        row = WebDriverWait(tbody, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'tr'))
        )
        cells = row.find_elements(By.TAG_NAME, 'td')
        
        # Clear default text and fill in prompt and expected
        # Click to focus and clear placeholder text
        cells[0].click()
        cells[0].clear()
        cells[0].send_keys(test_benchmark['prompts'][0]['prompt'])
        
        cells[1].click()
        cells[1].clear()
        cells[1].send_keys(test_benchmark['prompts'][0]['expected'])
        
        # Select model
        model_list = self.driver.find_element(By.ID, 'modelList')
        model_checkbox = model_list.find_element(By.XPATH, f"//input[@type='checkbox' and @value='{test_benchmark['models'][0]}']")        
        model_checkbox.click()
        
        # Submit benchmark
        run_btn = self.driver.find_element(By.ID, 'runBtn')
        run_btn.click()
        
        try:
            alert = self.driver.switch_to.alert
            alert.accept()
        except:
            pass  # No alert present
        
        # 2. Verify initial "in progress" status
        benchmark_card = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-status="in-progress"]'))
        )
        status_badge = benchmark_card.find_element(By.CLASS_NAME, 'status-badge')
        self.assertEqual(status_badge.text, 'In Progress')
        
        # 3. Wait for completion and verify status change
        completed_card = WebDriverWait(self.driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-status="complete"]'))
        )
        status_badge = completed_card.find_element(By.CLASS_NAME, 'status-badge')
        self.assertEqual(status_badge.text, 'Complete')
        
        # Store the benchmark ID for later verification
        benchmark_id = completed_card.get_attribute('data-benchmark-id')
        
        # 4. Refresh page and verify status persists
        self.driver.refresh()
        
        # Wait for page to reload and find our benchmark
        refreshed_card = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f'[data-benchmark-id="{benchmark_id}"]'))
        )
        status_badge = refreshed_card.find_element(By.CLASS_NAME, 'status-badge')
        
        # Verify status is still complete
        self.assertEqual(status_badge.text, 'Complete')
        self.assertEqual(refreshed_card.get_attribute('data-status'), 'complete')
        
        # 5. Verify in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM benchmarks WHERE id = ?", 
            (benchmark_id,)
        )
        db_status = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(db_status, 'complete')

if __name__ == '__main__':
    unittest.main()
