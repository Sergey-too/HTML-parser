from selenium import webdriver
from selenium_stealth import stealth  
from selenium.webdriver.common.by import By
import time
from datetime import datetime
import re
import pyodbc


# ==================== НАСТРОЙКИ ====================
DB_CONFIG = {
    'server': '192.168.0.110,1433',
    'database': 'GardenDB',
    'username': 'sa',
    'password': 'KBiPgardeN1',
    'driver': 'ODBC Driver 17 for SQL Server'
}

CITIES = {
    "Минск": {"id": 26851},
    "Брест": {"id": 33008},
    "Витебск": {"id": 26666},
    "Гомель": {"id": 33041},
    "Гродно": {"id": 26820},
    "Могилев": {"id": 26862}
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
            # Температура (формат: -5..-4)
            if '..' in line and 'temperature' not in current_day:
                current_day['temperature'] = line.replace('+', '')
            
            # Ветер (упрощенная проверка - если есть " - " или "(")
            elif (' - ' in line or '(' in line) and 'wind' not in current_day:
                # Проверяем что это не влажность (в влажности тоже есть " - ")
                if not any(char.isdigit() for char in line.replace(' ', '').replace('-', '')):
                    # Если нет цифр, это не ветер
                    pass
                else:
                    current_day['wind'] = line
            
            # Направление ветра (отдельно стоящие 1-3 символа)
            elif len(line) <= 3 and line not in ['падает', 'растёт'] and 'wind_dir' not in current_day:
                wind_dirs = ['С', 'Ю', 'З', 'В', 'С-3', 'Ю-3', '3', 'С-В', 'Ю-З', 'С-З', 'Ю-В']
                if any(wind_dir in line for wind_dir in wind_dirs):
                    current_day['wind_dir'] = line
            
            # Погодные явления (с проверкой что это не ветер и не давление)
            elif (not any(char.isdigit() for char in line) or 
                  ('вот тут' in line)) and len(line) > 3 and 'weather' not in current_day:
                # Исключаем направления ветра
                wind_dirs = ['С', 'Ю', 'З', 'В', 'С-3', 'Ю-3', '3', 'С-В', 'Ю-З', 'С-З', 'Ю-В']
                if not any(wind_dir in line for wind_dir in wind_dirs):
                    current_day['weather'] = line.lower()
            
            # Давление (4 цифры)
            elif re.match(r'^\d{3,4}$', line.replace(' ', '')) and 'pressure' not in current_day:
                current_day['pressure'] = line.replace(' ', '')
            
            # Тренд давления
            elif line in ['падает', 'растёт'] and 'pressure_trend' not in current_day:
                current_day['pressure_trend'] = line
            
            # Влажность (формат: 71-93)
            elif re.match(r'^\d+-\d+$', line.replace(' ', '')) and 'humidity' not in current_day:
                current_day['humidity'] = line.replace(' ', '')
            
            # Осадки (число с точкой или без)
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


# ==================== СОХРАНЕНИЕ В БД ====================
def save_weather_to_db(city_name, weather_data):
    """СОХРАНЯЕТ ДАННЫЕ В БД - УДАЛЯЕТ СТАРОЕ, ВСТАВЛЯЕТ НОВОЕ"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(f"\n💾 Сохраняю данные для {city_name} в БД...")
        
        # 1. Получаем region_id для города
        cursor.execute("SELECT id FROM regions WHERE name = ?", city_name)
        region_row = cursor.fetchone()
        
        if not region_row:
            print(f"❌ Город {city_name} не найден в таблице regions")
            return
        
        region_id = region_row[0]
        
        # 2. Собираем данные для вставки
        data_to_insert = []
        dates_to_delete = []
        
        for day in weather_data:
            # Парсим дату из "вт, 30.12.2025" в "2025-12-30"
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
            
            # Добавляем дату для удаления
            dates_to_delete.append(db_date)
            
            # Подготавливаем данные для вставки
            temperature = day.get('temperature', '')
            humidity = day.get('humidity', '')
            precipitation = day.get('precipitation', '')
            wind = day.get('wind', '')
            
            # Формируем condition
            condition_parts = []
            if 'weather' in day:
                condition_parts.append(day['weather'])
            if 'pressure' in day:
                condition_parts.append(f"давление: {day['pressure']}")
            condition = ", ".join(condition_parts)
            
            data_to_insert.append((
                region_id,
                db_date,
                str(temperature) if temperature else None,
                str(humidity) if humidity else None,
                str(precipitation) if precipitation else None,
                str(wind) if wind else None,
                condition[:1000] if condition else None
            ))
        
        # 3. УДАЛЯЕМ старые данные для этих дат
        if dates_to_delete:
            placeholders = ','.join(['?'] * len(dates_to_delete))
            delete_sql = f"""
                DELETE FROM weather 
                WHERE region_id = ? 
                AND date IN ({placeholders})
            """
            cursor.execute(delete_sql, [region_id] + dates_to_delete)
            print(f"   🗑️  Удалено старых записей: {cursor.rowcount}")
        
        # 4. ВСТАВЛЯЕМ новые данные
        if data_to_insert:
            insert_sql = """
                INSERT INTO weather 
                (region_id, date, temperature, humidity, precipitation, wind, condition)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            cursor.executemany(insert_sql, data_to_insert)
            print(f"   ✅ Вставлено новых записей: {len(data_to_insert)}")
        
        conn.commit()
        print(f"🎯 Данные для {city_name} успешно обновлены в БД")
        
    except Exception as e:
        print(f"❌ Ошибка при сохранении в БД: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()


# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def search_data(name, url):
    """Сбор и сохранение данных"""
    driver = None  
    try:
        driver = init_webdriver()  
        driver.get(url)
        time.sleep(10)

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
        
        # СОХРАНЕНИЕ В БД
        save_weather_to_db(name, processed_city)
        
    except Exception as e:
        print(f"❌ ОШИБКА при получении данных для {name}: {e}")
        
    finally:
        if driver:  
            driver.quit()


# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    # Установи библиотеки: pip install selenium selenium-stealth pyodbc
    
    print("🚀 ЗАПУСК ПАРСЕРА ПОГОДЫ")
    print("=" * 60)
    
    # Запускаем парсинг для всех городов
    search_data("Минск", "https://pogoda.by/weather/numerical-weather-day/26851")
    search_data("Брест", "https://pogoda.by/weather/numerical-weather-day/33008")
    search_data("Витебск", "https://pogoda.by/weather/numerical-weather-day/26666")
    search_data("Гомель", "https://pogoda.by/weather/numerical-weather-day/33041")
    search_data("Гродно", "https://pogoda.by/weather/numerical-weather-day/26820")
    search_data("Могилев", "https://pogoda.by/weather/numerical-weather-day/26862")
    
    
    print("\n" + "=" * 60)
    print("✅ ВСЕ ДАННЫЕ СОБРАНЫ И СОХРАНЕНЫ В БД")
    print("=" * 60)