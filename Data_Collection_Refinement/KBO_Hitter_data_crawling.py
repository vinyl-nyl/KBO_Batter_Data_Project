from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import pandas as pd
import time

# 크롬드라이버 실행
driver = webdriver.Chrome()
driver.implicitly_wait(10)

# KBO 웹페이지 이동
base_url = 'https://www.koreabaseball.com/Record/Player/HitterBasic/Basic1.aspx?sort=HRA_RT'
driver.get(base_url)

# "정규시즌" 선택
def select_regular_season(driver):
    try:
        dropdown = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_ddlSeries_ddlSeries')
        dropdown.click()
        dropdown.find_element(By.XPATH, ".//option[contains(text(), 'KBO 정규시즌')]").click()
        time.sleep(2)  # 페이지 로드 대기
    except Exception as e:
        print(f"Error selecting regular season: {e}")

# 특정 연도를 선택
def select_year(driver, year):
    try:
        year_dropdown = Select(driver.find_element(By.ID, 'cphContents_cphContents_cphContents_ddlSeason_ddlSeason'))
        year_dropdown.select_by_visible_text(str(year))
        time.sleep(2)  # 페이지 로드 대기
    except Exception as e:
        print(f"Error selecting year {year}: {e}")

# 특정 팀을 선택
def select_team(driver, team):
    try:
        team_dropdown = Select(driver.find_element(By.ID, 'cphContents_cphContents_cphContents_ddlTeam_ddlTeam'))
        team_dropdown.select_by_visible_text(team)
        time.sleep(2)  # 페이지 로드 대기
    except Exception as e:
        print(f"Team '{team}' not found. Skipping to the next team.")
        raise e

# 테이블 데이터 추출
def extract_table_data(driver):
    try:
        table = driver.find_element(By.CSS_SELECTOR, 'div.record_result > table')
        return pd.read_html(table.get_attribute('outerHTML'))[0]
    except Exception as e:
        print(f"Error extracting table data: {e}")
        return None

# 특정 페이지로 이동
def go_to_page(driver, page_number):
    try:
        page_button = driver.find_element(
            By.XPATH,
            f"//a[contains(@href, '__doPostBack') and contains(text(), '{page_number}')]"
        )
        driver.execute_script("arguments[0].click();", page_button)
        time.sleep(2)  # 페이지 로드 대기
    except Exception as e:
        print(f"Error navigating to page {page_number}: {e}")

# 모든 페이지 데이터 수집 (446타석 이상 필터 적용)
def scrape_all_pages(driver):
    all_data = []
    page_number = 1

    while True:
        print(f"Scraping page {page_number}...")

        # 현재 페이지 데이터 추출
        df = extract_table_data(driver)
        if df is not None:
            # 'PA' 열이 있는지 확인하고 446타석 이상 데이터 필터링
            if 'PA' in df.columns:
                df['PA'] = pd.to_numeric(df['PA'], errors='coerce')  # PA 열 숫자로 변환
                df = df[df['PA'] >= 446]  # 446타석 이상 필터링
                all_data.append(df)
        else:
            print(f"No data found on page {page_number}. Stopping scraper.")
            break

        try:
            # 다음 페이지 버튼을 확인
            next_page_button = driver.find_element(
                By.XPATH, f"//a[contains(@href, '__doPostBack') and contains(text(), '{page_number + 1}')]"
            )
            if next_page_button:
                go_to_page(driver, page_number + 1)
                page_number += 1
            else:
                print("No more pages to navigate.")
                break
        except Exception:
            print("Reached the last page.")
            break

    # 모든 데이터를 하나의 DataFrame으로 병합
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

# 팀별 데이터 수집
def scrape_team_data(driver, year, teams):
    all_team_data = []
    for team in teams:
        print(f"Scraping data for {team} in {year}...")
        try:
            select_team(driver, team)  # 팀 선택
            team_data = scrape_all_pages(driver)  # 각 팀별로 데이터 크롤링
            if team_data is not None:
                team_data['Year'] = year
                team_data['Team'] = team
                all_team_data.append(team_data)
        except Exception as e:
            print(f"Skipping team {team} due to an error: {e}")
            continue  # 예외 발생 시 다음 팀으로 넘어감

        # 페이지를 다시 첫 번째 페이지로 초기화
        driver.refresh()
        time.sleep(3)
        select_year(driver, year)

    if all_team_data:
        return pd.concat(all_team_data, ignore_index=True)
    return None

# 전체 데이터를 연도별로 수집
def scrape_all_data(driver, start_year, end_year, teams):
    all_data = []
    for year in range(start_year, end_year + 1):
        print(f"Scraping data for the year {year}...")
        select_year(driver, year)
        yearly_data = scrape_team_data(driver, year, teams)
        if yearly_data is not None:
            all_data.append(yearly_data)
    if all_data:
        combined_data = pd.concat(all_data, ignore_index=True)
        # 팀명 변경: SK -> SSG, 넥센/우리/히어로즈 -> 키움
        combined_data['Team'] = combined_data['Team'].replace({
            'SK': 'SSG',
            '넥센': '키움',
            '우리': '키움',
            '히어로즈': '키움'
        })
        return combined_data
    return None

# 팀 목록 정의 (드롭다운에서 제공되는 팀 이름과 일치해야 함)
teams = ["KIA", "삼성", "LG", "두산", "KT", "SSG", "SK", "롯데", "한화", "NC", "키움", "우리", "히어로즈", "넥센"]

# 정규시즌 데이터 선택
select_regular_season(driver)

# 전체 데이터 수집
final_data = scrape_all_data(driver, 2004, 2024, teams)

# 결과 저장
if final_data is not None:
    final_data.to_csv('kbo_Hitter_data.csv', encoding='utf-8-sig', index=False)
    print("Data saved to kbo_Hitter_data.csv")
else:
    print("No data scraped.")

# 드라이버 종료
driver.quit()