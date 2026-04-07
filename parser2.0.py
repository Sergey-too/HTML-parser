from selenium import webdriver
from selenium_stealth import stealth  
from selenium.webdriver.common.by import By
import time
from datetime import datetime
import re
import pyodbc


# ==================== НАСТРОЙКИ ====================
DB_CONFIG = {
    'server': 'localhost,1433',
    'database': 'GardenDB',
    'username': 'sa',
    'password': 'KBiPgardeN1',
    'driver': 'ODBC Driver 17 for SQL Server'
}

# ==================== БАЗОВЫЕ ФУНКЦИИ ====================
def get_db_connection():
    """Подключение к БД"""
    conn_str = (
        f"DRIVER={{{DB_CONFIG['driver']}}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']};"
        "Trusted_Connection=no;"
    )
    return pyodbc.connect(conn_str)


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


# ==================== ПАРСИНГ ДАННЫХ ====================
def process_weather_data(input_text):
    """Обработка погодных данных в нужный формат для weather_new"""
    
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
            if '..' in line and 'temperature_min' not in current_day:
                temp_clean = line.replace('+', '')
                temp_parts = temp_clean.split('..')
                if len(temp_parts) == 2:
                    current_day['temperature_min'] = temp_parts[0].strip()
                    current_day['temperature_max'] = temp_parts[1].strip()

            # Погодные явления (пропускаем)
            elif line in ['Продолжительные осадки', 'Кратковременные осадки', 'Облачно', 'Временами осадки']:
                pass
            
            # Ветер и порывы
            elif '-' in line and 'м/с' not in line and '(' in line and 'wind_min' not in current_day:
                wind_match = re.search(r'(\d+)\s*-\s*(\d+)\s*\((\d+)\)', line)
                if wind_match:
                    current_day['wind_min'] = wind_match.group(1)
                    current_day['wind_max'] = wind_match.group(2)
                    current_day['gusts_of_wind'] = wind_match.group(3)

            # Давление (1 006)
            elif re.match(r'^\d+\s+\d+$', line) and 'pressure' not in current_day:
                pressure_clean = line.replace(' ', '')
                current_day['pressure'] = pressure_clean
            
            # Направление ветра (пропускаем)
            elif line in ['С-З', 'С', 'В', 'Ю-З', 'Ю-В', 'З']:
                pass
            
            # Давление и тренд (пропускаем)
            elif re.match(r'^\d{1,2}\s\d{3}$', line) or line in ['растёт', 'падает', 'не измен.']:
                pass

            # Влажность
            elif re.match(r'^\d+\s*-\s*\d+$', line) and 'humidity_min' not in current_day:
                humidity_parts = re.split(r'\s*-\s*', line)
                if len(humidity_parts) == 2:
                    current_day['humidity_min'] = humidity_parts[0].strip()
                    current_day['humidity_max'] = humidity_parts[1].strip()
            
            # Осадки
            elif re.match(r'^\d+(\.\d+)?$', line) and 'precipitation' not in current_day:
                current_day['precipitation'] = line
                processed_days.append(current_day)
                current_day = {}
        
        i += 1

    return processed_days

def format_output(data_list):
    formatted_lines = []
    
    for day_data in data_list:
        line_parts = [
            day_data.get('date', ''),
            day_data.get('temperature_min', ''),      
            day_data.get('temperature_max', ''),  
            day_data.get('humidity_min', ''),    
            day_data.get('humidity_max', ''),
            day_data.get('precipitation', ''),
            day_data.get('wind_min', ''),
            day_data.get('wind_max', ''), 
            day_data.get('gusts_of_wind', ''),
            day_data.get('pressure', '')  
        ]
                
        formatted_line = '|'.join(line_parts)
        formatted_lines.append(formatted_line)
    
    return formatted_lines


# ==================== СОХРАНЕНИЕ В БД ====================
def save_weather_to_db(city_name, weather_data):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(f"\nСохраняю данные для {city_name} в БД...")
        
        cursor.execute("SELECT id FROM regions WHERE name = ?", city_name)
        region_row = cursor.fetchone()
        
        if not region_row:
            print(f"Город {city_name} не найден в таблице regions")
            return
        
        region_id = region_row[0]
        
        data_to_insert = []
        dates_to_delete = []
        
        for day in weather_data:
            date_str = day.get('date', '')
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_str)
            
            if date_match:
                date_part = date_match.group(1)
                try:
                    db_date = datetime.strptime(date_part, '%d.%m.%Y').strftime('%Y-%m-%d')
                except:
                    db_date = date_part
            else:
                db_date = date_str
            
            dates_to_delete.append(db_date)

            data_to_insert.append((
                region_id,
                db_date,
                day.get('temperature_min', ''),
                day.get('temperature_max', ''),
                day.get('humidity_min', ''),
                day.get('humidity_max', ''),
                day.get('precipitation', ''),
                day.get('wind_min', ''),
                day.get('wind_max', ''),
                day.get('gusts_of_wind', ''),
                day.get('pressure', '')  
            ))

        if dates_to_delete:
            placeholders = ','.join(['?'] * len(dates_to_delete))
            delete_sql = f"""
                DELETE FROM weather_new
                WHERE region_id = ? 
                AND date IN ({placeholders})
            """
            cursor.execute(delete_sql, [region_id] + dates_to_delete)
            print(f"Удалено старых записей: {cursor.rowcount}")
        
        if data_to_insert:
            insert_sql = """
                INSERT INTO weather_new
                (region_id, date, temperature_min, temperature_max, 
                 humidity_min, humidity_max, precipitation, 
                 wind_min, wind_max, gusts_of_wind, pressure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.executemany(insert_sql, data_to_insert)
            print(f"Вставлено новых записей: {len(data_to_insert)}")
        
        conn.commit()
        print(f"Данные для {city_name} успешно обновлены в БД")
        
    except Exception as e:
        print(f"Ошибка при сохранении в БД: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def search_data(name, url):
    driver = None  
    try:
        driver = init_webdriver()  
        driver.get(url)
        time.sleep(5)

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

        save_weather_to_db(name, processed_city)
        
    except Exception as e:
        print(f"ОШИБКА при получении данных для {name}: {e}")
        
    finally:
        if driver:  
            driver.quit()


# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    
    print("ЗАПУСК ПАРСЕРА ПОГОДЫ")
    print("=" * 60)
    
    search_data("Минск", "https://pogoda.by/weather/numerical-weather-day/26851")
    search_data("Брест", "https://pogoda.by/weather/numerical-weather-day/33008")
    search_data("Витебск", "https://pogoda.by/weather/numerical-weather-day/26666")
    search_data("Гомель", "https://pogoda.by/weather/numerical-weather-day/33041")
    search_data("Гродно", "https://pogoda.by/weather/numerical-weather-day/26820")
    search_data("Могилев", "https://pogoda.by/weather/numerical-weather-day/26862")
    
    print("\n" + "=" * 60)
    print("ВСЕ!")
    print("=" * 60)