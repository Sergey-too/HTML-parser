from selenium import webdriver
from selenium_stealth import stealth  
from selenium.webdriver.common.by import By
import time
from datetime import datetime
import re
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def init_webdriver():
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized") 
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-cache")
    options.add_argument("--incognito") 
    
    driver = webdriver.Chrome(options=options)
    
    stealth(driver,
            languages=["ru-RU", "ru"],  
            platform="Win32",           
            vendor="Google Inc.",       
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )
    
    return driver


def search_data(name, url):
    driver = None  
    try:
        driver = init_webdriver()  
        driver.get(url)
        time.sleep(8)

        table_search = driver.find_element(By.CLASS_NAME, 'container-numeral-table') 
        tbody = table_search.find_element(By.TAG_NAME, "tbody")

        dataCity = tbody.find_elements(By.TAG_NAME, "tr")

        all_text_city = ""
        for d in dataCity:
            all_text_city += d.text + "\n"

        processed_city = process_weather_data(all_text_city)

        print("=" * 60)
        print(f"Обработанные данные {name}:")
        for line in format_output(processed_city):
            print(line)
        print()  
        
    except Exception as e:
        print(f"ОШИБКА при получении данных для {name}: {e}")
        
    finally:
        if driver:  
            driver.quit()


#----------------------------------------------------------------------------------
def process_weather_data(input_text):
    """Обработка погодных данных в нужный формат"""
    
    lines = [line.strip() for line in input_text.strip().split('\n') if line.strip()]
    
    processed_days = []
    current_day = {}
    
    date_pattern = re.compile(r'^([а-я]+),\s*(\d{1,2}\.\d{2})$')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        date_match = date_pattern.match(line)
        
        if date_match:
            if current_day:
                processed_days.append(current_day)
                current_day = {}
            
            day_name, date_str = date_match.groups()
            current_year = datetime.now().year
            full_date = f"{date_str}.{current_year}"
            formatted_date = f"{day_name}, {full_date}"
            current_day['date'] = formatted_date
            i += 1
            continue
        
        if 'date' in current_day:
            # Температура
            if '..' in line and 'temperature' not in current_day:
                current_day['temperature'] = line.replace('+', '')
            
            # Ветер (полный формат с направлением)
            elif ' - ' in line and '(' in line and ')' in line and 'wind' not in current_day:
                current_day['wind'] = line
            
            # Направление ветра (отдельно стоящие 1-3 символа)
            elif len(line) <= 3 and line not in ['падает', 'растёт'] and 'wind_dir' not in current_day:
                # Проверяем что это действительно направление ветра (С, Ю, З, В или их комбинации)
                wind_dirs = ['С', 'Ю', 'З', 'В', 'С-3', 'Ю-3', '3', 'С-В', 'Ю-З', 'С-З', 'Ю-В']
                if any(wind_dir in line for wind_dir in wind_dirs):
                    current_day['wind_dir'] = line
            
            # Погодные явления
            elif not any(char.isdigit() for char in line) and len(line) > 3 and 'weather' not in current_day:
                current_day['weather'] = line.lower()
            
            # Давление (4 цифры)
            elif re.match(r'^\d{3,4}$', line.replace(' ', '')) and 'pressure' not in current_day:
                current_day['pressure'] = line.replace(' ', '')
            
            # Тренд давления
            elif line in ['падает', 'растёт'] and 'pressure_trend' not in current_day:
                current_day['pressure_trend'] = line
            
            # Влажность
            elif ' - ' in line and any(char.isdigit() for char in line) and 'humidity' not in current_day:
                current_day['humidity'] = line.replace(' ', '')
            
            # Осадки
            elif re.match(r'^\d+(\.\d+)?$', line) and 'precipitation' not in current_day:
                current_day['precipitation'] = line
                
                # Добавляем давление с трендом если они были
                if 'pressure' in current_day and 'pressure_trend' in current_day:
                    current_day['pressure'] = f"{current_day['pressure']} {current_day['pressure_trend']}"
                
                # Добавляем ветер с направлением если они были
                if 'wind' in current_day and 'wind_dir' in current_day:
                    current_day['wind'] = f"{current_day['wind']} {current_day['wind_dir']}"
                
                processed_days.append(current_day)
                current_day = {}
        
        i += 1

    if current_day:
        # Обрабатываем последний день
        if 'pressure' in current_day and 'pressure_trend' in current_day:
            current_day['pressure'] = f"{current_day['pressure']} {current_day['pressure_trend']}"
        if 'wind' in current_day and 'wind_dir' in current_day:
            current_day['wind'] = f"{current_day['wind']} {current_day['wind_dir']}"
        processed_days.append(current_day)
    
    return processed_days

def format_output(data_list):
    formatted_lines = []
    
    for day_data in data_list:
        pressure = day_data.get('pressure', '')
        
        line_parts = [
            day_data.get('date', ''),
            day_data.get('temperature', ''),      
            day_data.get('weather', ''),          
            day_data.get('wind', ''),             
            pressure,         
            day_data.get('humidity', ''),         
            day_data.get('precipitation', '')     
        ]
                
        formatted_line = '|'.join(line_parts)
        formatted_lines.append(formatted_line)
    
    return formatted_lines
#--------------------------------------------------------------------------------

search_data("Минск", "https://pogoda.by/weather/numerical-weather-day/26851")
search_data("Брест", "https://pogoda.by/weather/numerical-weather-day/33008")
search_data("Витебск", "https://pogoda.by/weather/numerical-weather-day/26666")
search_data("Гомель", "https://pogoda.by/weather/numerical-weather-day/33041")
search_data("Гродно", "https://pogoda.by/weather/numerical-weather-day/26820")
search_data("Могилев", "https://pogoda.by/weather/numerical-weather-day/26862")

