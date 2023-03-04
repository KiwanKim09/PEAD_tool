import re
import os
import datetime
from datetime import datetime
import requests
import dart_fss
from dart_fss.filings.reports import Report

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from pykrx import stock
import pandas as pd

__TOKEN = "5948138313:AAF4lys6I8vcghJ-h6fHYXQcRPh86TiafUI"
__chat_id = -1001820286028
ERROR_MSG = "*** (ERROR) 파싱 오류 ***"


class DartListInfo:

    def __init__(self, rows: list, has_more: bool):
        self.rows = rows
        self.has_more = has_more

    def __str__(self) -> str:
        return f'DartListInfo(rows={self.rows}, has_more={self.has_more})'


class DartRow:

    def __init__(self, num: int, corp_cls: str, corp_name: str, report_nm: str, report_link: str, rcept_dt: str, tag: str):
        self.num = num
        self.corp_cls = corp_cls
        self.corp_name = corp_name
        self.report_nm = report_nm
        self.report_link = report_link
        self.rcept_dt = rcept_dt
        self.tag = tag

    def __str__(self) -> str:
        return f'DartRow(num={self.num}, corp_cls={self.corp_cls}, company={self.corp_name}, report_name={self.report_nm}, report_link={self.report_link}, report_date={self.rcept_dt}, tag={self.tag})\n'


class OverShootingDescription:

    def __init__(self, net_revenue: int, net_revenue_expression: str):
        self.net_revenue = net_revenue
        self.net_revenue_expression = net_revenue_expression

    def __str__(self) -> str:
        return f'OverShootingDescription(net_revenue={self.net_revenue}, net_revenue_expression={self.net_revenue_expression})'


class Account:

    def __init__(self, exist: bool, this_qtr: str, prev_qtr: str, this_qtr_prev_yr: str, cum_this_qtr: str,
                 cum_prev_qtr: str, cum_this_qtr_prev_yr: str, qoq: str, yoy: str, reason: str):
        self.exist = exist
        # This Year data
        # this_qtr_data
        # this_qtr_cumulative_data

        # QoQ data
        # right_before_qtr_data
        # right_before_qtr_cumalative_data

        # YoY data
        # prev_yr_same_qtr_data
        # prev_yr_same_qtr_cumalative_data

        # this year, cum
        self.this_qtr = this_qtr  # this_qtr_data
        self.prev_qtr = prev_qtr  # right_before_qtr_data
        self.this_qtr_prev_yr = this_qtr_prev_yr  # prev_yr_same_qtr_data

        self.cum_this_qtr = cum_this_qtr  # this_qtr_cumulative_data
        self.cum_prev_qtr = cum_prev_qtr  # right_before_qtr_cumalative_data
        self.cum_this_qtr_prev_yr = cum_this_qtr_prev_yr  # prev_yr_same_qtr_cumalative_data

        self.qoq = qoq
        self.yoy = yoy
        self.reason = reason

    def __str__(self) -> str:
        return f'Account(exist={self.exist}, this_qtr={self.this_qtr}, prev_qtr={self.prev_qtr}, this_qtr_prev_yr={self.this_qtr_prev_yr}, cum_this_qtr={self.cum_this_qtr}, cum_prev_qtr={self.cum_prev_qtr}, cum_this_qtr_prev_yr={self.cum_this_qtr_prev_yr})\n'


class EarningData:

    def __init__(self, report_date: str, report_type: str, report_name: str, report_link: str, company_name: str,
                 stock_code: str, unit: int, label: list, rv: Account, op: Account, np: Account, cnp: Account):
        self.report_date = report_date
        self.report_type = report_type
        self.report_name = report_name
        self.report_link = report_link
        self.company_name = company_name
        self.stock_code = stock_code
        self.unit = unit
        self.label = label
        self.rv = rv
        self.op = op
        self.np = np
        self.cnp = cnp

    def __str__(self) -> str:
        return f'DartRow(report_date={self.report_date}, report_type={self.report_type}, report_name={self.report_name}, report_link={self.report_link}, company_name={self.company_name}, stock_code={self.stock_code} unit={self.unit}, label={self.label}, rv={self.rv}, op={self.op}, np={self.np}, cnp={self.cnp})\n'


def get_disclosure(date_to_process: str, page: int, size: int, foundReportLinks: list, lastReportLink:str) -> DartListInfo:
    """
    YYYYmmDD 형식의 시작/종료 날짜를 입력받고, 페이지 번호, 한 페이지의 크기를 입력 받는다.
    공시 리스트 정보를 반환한다.
    """
    if size > 100:
        raise Exception('size value should be less than 100.')
    headers = {
        'accept': 'text/html, */*; q=0.01',
        'accept-language': 'en-US,en;q=0.9,ko;q=0.8',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'sec-ch-ua': '"Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'x-requested-with': 'XMLHttpRequest',
        'cookie': 'WMONID=NoDdZR4L6wm; PCID=16412179951314069874594; RC_RESOLUTION=2560*1440; RC_COLOR=24; popToday=Y; JSESSIONID=sVaXCz7eJy16pLw6Dkb72jCkV4uxB81C0FgrAtS6rdBRI7U87w7nHId6C46Nxr52.ZG1fZGFydC9kYXJ0Ml9kYXJ0X21zMw==',
        'Referer': 'https://dart.fss.or.kr/dsab007/main.do',
        'Referrer-Policy': 'strict-origin-when-cross-origin'
    }

    # text -> http post: https://www.percederberg.net/tools/text_converter.html
    # 매출액또는손익30%(대규모법인은15%)이상변경//매출액또는손익구조30%(대규모법인15%)미만변경(자율공시)//매출액또는손익구조30%(대규모법인은15%)미만변동(자율공시)//매출액또는손익구조30%(대규모법인은15%)이상변경//매출액또는손익구조30%(대규모법인은15%)이상변동
    # data = 'currentPage={}&maxResults={}&maxLinks=10&sort=date&series=desc&textCrpCik=&lateKeyword=&keyword=&reportNamePopYn=Y&textkeyword=&businessCode=all&autoSearch=N&option=report&textCrpNm=&reportName=%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B530%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B8%EC%9D%8015%25)%EC%9D%B4%EC%83%81%EB%B3%80%EA%B2%BD%2F%2F%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B5%EA%B5%AC%EC%A1%B030%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B815%25)%EB%AF%B8%EB%A7%8C%EB%B3%80%EA%B2%BD(%EC%9E%90%EC%9C%A8%EA%B3%B5%EC%8B%9C)%2F%2F%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B5%EA%B5%AC%EC%A1%B030%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B8%EC%9D%8015%25)%EB%AF%B8%EB%A7%8C%EB%B3%80%EB%8F%99(%EC%9E%90%EC%9C%A8%EA%B3%B5%EC%8B%9C)%2F%2F%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B5%EA%B5%AC%EC%A1%B030%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B8%EC%9D%8015%25)%EC%9D%B4%EC%83%81%EB%B3%80%EA%B2%BD%2F%2F%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B5%EA%B5%AC%EC%A1%B030%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B8%EC%9D%8015%25)%EC%9D%B4%EC%83%81%EB%B3%80%EB%8F%99&tocSrch=&textCrpNm2=&textPresenterNm=&startDate={}&endDate={}&decadeType=&finalReport=recent&businessNm=%EC%A0%84%EC%B2%B4&corporationType=all&closingAccountsMonth=all&tocSrch2='.format(page, size, start_date, end_date)

    # 연결재무제표기준영업(잠정)실적(공정공시)//영업(잠정)실적(공정공시)
    # data = 'currentPage={}&maxResults={}&maxLinks=10&sort=date&series=desc&textCrpCik=&lateKeyword=&keyword=&reportNamePopYn=Y&textkeyword=&businessCode=all&autoSearch=N&option=report&textCrpNm=&reportName=%EC%97%B0%EA%B2%B0%EC%9E%AC%EB%AC%B4%EC%A0%9C%ED%91%9C%EA%B8%B0%EC%A4%80%EC%98%81%EC%97%85(%EC%9E%A0%EC%A0%95)%EC%8B%A4%EC%A0%81(%EA%B3%B5%EC%A0%95%EA%B3%B5%EC%8B%9C)%2F%2F%EC%98%81%EC%97%85(%EC%9E%A0%EC%A0%95)%EC%8B%A4%EC%A0%81(%EA%B3%B5%EC%A0%95%EA%B3%B5%EC%8B%9C)&tocSrch=&textCrpNm2=&textPresenterNm=&startDate={}&endDate={}&decadeType=&finalReport=recent&businessNm=%EC%A0%84%EC%B2%B4&corporationType=all&closingAccountsMonth=all&tocSrch2='.format(page, size, start_date, end_date)

    # 변동공시, 잠정공시, 보고서 모두
    data = 'currentPage={}&maxResults={}&maxLinks=10&sort=date&series=desc&textCrpCik=&lateKeyword=&keyword=&reportNamePopYn=Y&textkeyword=&businessCode=all&autoSearch=N&option=report&textCrpNm=&reportName=%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B530%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B8%EC%9D%8015%25)%EC%9D%B4%EC%83%81%EB%B3%80%EA%B2%BD%2F%2F%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B5%EA%B5%AC%EC%A1%B030%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B815%25)%EB%AF%B8%EB%A7%8C%EB%B3%80%EA%B2%BD(%EC%9E%90%EC%9C%A8%EA%B3%B5%EC%8B%9C)%2F%2F%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B5%EA%B5%AC%EC%A1%B030%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B8%EC%9D%8015%25)%EB%AF%B8%EB%A7%8C%EB%B3%80%EB%8F%99(%EC%9E%90%EC%9C%A8%EA%B3%B5%EC%8B%9C)%2F%2F%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B5%EA%B5%AC%EC%A1%B030%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B8%EC%9D%8015%25)%EC%9D%B4%EC%83%81%EB%B3%80%EA%B2%BD%2F%2F%EB%A7%A4%EC%B6%9C%EC%95%A1%EB%98%90%EB%8A%94%EC%86%90%EC%9D%B5%EA%B5%AC%EC%A1%B030%25(%EB%8C%80%EA%B7%9C%EB%AA%A8%EB%B2%95%EC%9D%B8%EC%9D%8015%25)%EC%9D%B4%EC%83%81%EB%B3%80%EB%8F%99%2F%2F%EC%97%B0%EA%B2%B0%EC%9E%AC%EB%AC%B4%EC%A0%9C%ED%91%9C%EA%B8%B0%EC%A4%80%EC%98%81%EC%97%85(%EC%9E%A0%EC%A0%95)%EC%8B%A4%EC%A0%81(%EA%B3%B5%EC%A0%95%EA%B3%B5%EC%8B%9C)%2F%2F%EC%98%81%EC%97%85(%EC%9E%A0%EC%A0%95)%EC%8B%A4%EC%A0%81(%EA%B3%B5%EC%A0%95%EA%B3%B5%EC%8B%9C)%2F%2F%EB%B6%84%EA%B8%B0%EB%B3%B4%EA%B3%A0%EC%84%9C%2F%2F%EB%B0%98%EA%B8%B0%EB%B3%B4%EA%B3%A0%EC%84%9C%2F%2F%EC%82%AC%EC%97%85%EB%B3%B4%EA%B3%A0%EC%84%9C&tocSrch=&textCrpNm2=&textPresenterNm=&startDate={}&endDate={}&decadeType=&finalReport=recent&businessNm=%EC%A0%84%EC%B2%B4&corporationType=all&closingAccountsMonth=all&tocSrch2='.format(page, size, date_to_process, date_to_process)

    r = requests.post('https://dart.fss.or.kr/dsab007/detailSearch.ax', headers=headers, data=data, verify=False)
    soup = BeautifulSoup(r.text, 'html.parser')

    tr_list = soup.find(id='tbody').find_all('tr')
    # print(len(tr_list))

    rows = []
    for tr in tr_list:
        td_list = tr.find_all('td')
        number = td_list[0].text.strip()
        corp_cls = td_list[1].find_all()[1].text
        corp_name = td_list[1].find('a').text.strip()
        report_nm = clean_blank(td_list[2].text.strip())
        t_link = td_list[2].find('a').extract()
        report_link = t_link.get('href')
        rcept_dt = td_list[4].text.strip()
        tag = td_list[5].text.strip()

        print('get_disclosure: found ', corp_name)

        # 찾다가 lastReportLink가 나오면 break
        if(report_link == lastReportLink):
            break

        # 날짜가 date_to_process를 넘어가면 break
        if(rcept_dt.replace('.','') < date_to_process.replace('-', '')):
            break

        if(report_link not in foundReportLinks):
            rows.append(DartRow(number, corp_cls, corp_name, report_nm, report_link, rcept_dt, tag))
            print('get_disclosure: appended ', corp_name)

    page_info = soup.find(id='psWrap').find('div', class_='pageInfo').text
    # page_info sample : [1/167] [총 2,496건]
    regex_gorups = re.search(r"\[(\d*)/(\d*)\]", page_info)

    return DartListInfo(rows=rows, has_more=(regex_gorups.group(1) != regex_gorups.group(2)))


def add_comma(origin_str: str):
    temp_str = ''
    if (origin_str[0] == '-'):
        temp_str = origin_str[0]
        origin_str = origin_str.replace('-', '')

    if (len(origin_str) >= 4):
        s1 = origin_str[0:len(origin_str) - 3]
        s2 = origin_str[len(origin_str) - 3:len(origin_str)]
        s1 = add_comma(s1)
        return temp_str + s1 + "," + s2
    else:
        return temp_str + origin_str


def apply_unit(value_str: str, unit: int):
    if (value_str == '-'):
        return value_str

    try:
        value = int(value_str.replace(',', '')) * unit
    except:
        value = int(value_str.replace('.', '')) * unit
    eok = int(value / 1e8)

    return add_comma(str(eok)) + '억'


def find_unit(unit_str: str):
    unit = 1
    if (unit_str.find("천원") != -1) or (unit_str.find("천 원") != -1):
        # 천원
        unit = 1000;
    elif (unit_str.find("백만원") != -1) or (unit_str.find("백만 원") != -1) or (unit_str.find("백 만 원") != -1):
        # 백만원
        unit = 1000000;
    elif (unit_str.find("억원") != -1) or (unit_str.find("억 원") != -1):
        # 억원
        unit = 100000000
    elif (unit_str.find("십억원") != -1) or (unit_str.find("십억 원") != -1) or (unit_str.find("십 억 원") != -1):
        # 십억원
        unit = 1000000000
    elif (unit_str.find("조원") != -1) or (unit_str.find("조 원") != -1):
        # 조원
        unit = 1000000000000
    return unit


def send_tele_msg(msg: str):
    # data = {"chat_id" : __chat_id, "text": msg }
    # url = f"https://api.telegram.org/bot{__TOKEN}/sendMessage?"
    # res = requests.post(url, json=data)
    print(msg)
    return


def fix_bracket_for_number(dirty: str):
    if dirty.startswith('(') and dirty.endswith(')'):
        dirty = dirty.replace('(', '-')
        dirty = dirty.replace(')', '')
    return dirty


def clean_blank(dirty: str):
    clean = dirty.replace('/n', '')
    clean = clean.replace('/t', '')
    clean = clean.replace(' ', '')
    clean = clean.replace('\n', '')
    clean = clean.replace('\r', '')
    clean = clean.replace('\t', '')
    return clean


def clean_string(dirty: str):
    clean = clean_blank(dirty)
    clean = clean.replace('(', '')
    clean = clean.replace(')', '')
    clean = clean.replace("'", "")
    clean = clean.replace('년', '.')
    clean = clean.replace('분기', 'Q')
    if clean.startswith("20"):
        clean = clean[2:]
    return clean


def get_xml_from_link(link: str):
    my_options = webdriver.ChromeOptions()
    my_options.add_argument('disable-gpu')  # GPU 사용 안함
    my_options.add_argument('lang=ko_KR')  # 언어 설정
    my_options.add_argument('headless')
    my_options.add_experimental_option('excludeSwitches', ['enable-logging'])  # 로그 출력 안함
    os.environ['WDM_LOG_LEVEL'] = '0'
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=my_options)
    driver.get(link)
    try:
        # element = WebDriverWait(driver, 5).until(
        #     EC.presence_of_element_located((By.CLASS_NAME, 'viewWrap'))
        # )  # 웹 브라우저가 정상적으로 로딩될 때까지 기다림
        iframe = driver.find_element(by=By.TAG_NAME, value='iframe')
        driver.switch_to.frame(iframe)
        tr_list = driver.find_elements(by=By.TAG_NAME, value='tr')
        return tr_list
    except TimeoutException:
        print('타임아웃: ', link)
    return


def parser_30pcnt_change(report: Report, market_cap: int, stock_code: str):
    report_date = report.rcept_dt
    report_type = None
    report_name = report.report_nm
    report_link = "https://dart.fss.or.kr" + report.report_link
    company_name = report.corp_name
    stock_code = stock_code
    unit = None
    label = []
    rv = Account(False, None, None, None, None, None, None, None, None, None)
    op = Account(False, None, None, None, None, None, None, None, None, None)
    np = Account(False, None, None, None, None, None, None, None, None, None)
    cnp = Account(False, None, None, None, None, None, None, None, None, None)
    reason_msg = ""

    # print()
    # print("corp_name: ", company_name)
    # print("report_name: ", report_name)
    # print("report_link: ", report_link)

    # market_cap = stock.get_market_cap("20230224").loc[report.stock_code]['시가총액']
    market_cap_str = add_comma(str(int(market_cap / 1e8))) + '억'
    entire_msg = datetime.now().strftime("%Y.%m.%d %H:%M:%S") + "\n" + \
                 "기업명: " + company_name + "(시가총액: " + market_cap_str + ")\n" + \
                 "공시일: " + report_date + "\n" + \
                 "보고서명: " + report_name

    tr_list = get_xml_from_link(report_link)

    got_type = got_unit = got_label = False
    got_rv = got_op = got_np = got_cnp = got_reason = False
    for tr in tr_list:
        # find type: 연결/개별
        if (not got_type):
            found_type_cons = (tr.text.find("연결") != -1)
            found_type_sepa = (tr.text.find("개별") != -1)
            if found_type_cons or found_type_sepa:
                if found_type_cons:
                    report_type = "연결"
                else:
                    report_type = "개별"
                got_type = True
                type_msg = "구분: " + report_type
                # print(type_msg)
                entire_msg = entire_msg + "\n" + type_msg + "\n\n"  # <<<<<
        # find unit: 원/천원/백만원/억원/조원
        if (not got_unit):
            found_unit = (tr.text.find("단위") != -1) and (tr.text.find("원") != -1)
            if found_unit:
                unit = find_unit(tr.text)
                got_unit = True
                # unit_msg = "unit: " + str(unit)
                # print(unit_msg)
                # entire_msg = entire_msg + "\n" + unit_msg #<<<<<
        # find label
        if (not got_label):
            found_label = tr.text.find("매출액 또는 손익구조") != -1
            if found_label:
                td_list = tr.find_elements(by=By.TAG_NAME, value='td')
                label.append(clean_string(td_list[1].text))
                label.append(clean_string(td_list[2].text))
                got_label = True
                # label_msg = "label: " + ', '.join(label)
                # print(label_msg)
                # entire_msg = entire_msg + "\n" + label_msg #<<<<<
                continue
        # find revenue
        if (got_type and got_unit and got_label) and (not got_rv):
            found_rv = tr.text.find("매출액") != -1
            if found_rv:
                td_list = tr.find_elements(by=By.TAG_NAME, value='td')
                rv.exist = found_rv
                rv.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list[1].text))
                rv.cum_this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td_list[2].text))
                rv.yoy = fix_bracket_for_number(clean_blank(td_list[4].text))
                got_rv = True
                # rv_msg = 'rv: [' + rv.cum_this_qtr + ', ' + rv.cum_this_qtr_prev_yr + ']'
                # print(rv_msg)
                # entire_msg = entire_msg + "\n" + rv_msg #<<<<<
                continue
        # find operating profit
        if (got_type and got_unit and got_label and got_rv) and (not got_op):
            found_op = tr.text.find("영업이익") != -1
            if found_op:
                td_list = tr.find_elements(by=By.TAG_NAME, value='td')
                op.exist = found_op
                op.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list[1].text))
                op.cum_this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td_list[2].text))
                op.yoy = fix_bracket_for_number(clean_blank(td_list[4].text))
                got_op = True
                # op_msg = 'op: [' + op.cum_this_qtr + ', ' + op.cum_this_qtr_prev_yr + ']'
                # print(op_msg)
                # entire_msg = entire_msg + "\n" + op_msg #<<<<<
                continue
        # find net profit
        if (got_type and got_unit and got_label and got_rv and got_op) and (not got_np):
            found_np = tr.text.find("당기순이익") != -1
            if found_np:
                td_list = tr.find_elements(by=By.TAG_NAME, value='td')
                np.exist = found_np
                np.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list[1].text))
                np.cum_this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td_list[2].text))
                np.yoy = fix_bracket_for_number(clean_blank(td_list[4].text))
                got_np = True
                # np_msg = 'np: [' + np.cum_this_qtr + ', ' + np.cum_this_qtr_prev_yr + ']'
                # print(np_msg)
                # entire_msg = entire_msg + "\n" + np_msg #<<<<<
                continue
        # find reason
        if (got_type and got_unit and got_label and got_rv and got_op and got_np) and (not got_reason):
            found_reason = tr.text.find("매출액 또는 손익구조 변동") != -1
            if found_reason:
                td_list = tr.find_elements(by=By.TAG_NAME, value='td')
                reason_msg = td_list[1].text.replace('\n\n', '\n')
                if(reason_msg.find('\n') != -1):
                    reason_msg = '\n' + reason_msg
                got_reason = True
                # np_msg = 'np: [' + np.cum_this_qtr + ', ' + np.cum_this_qtr_prev_yr + ']'
                # print(np_msg)
                # entire_msg = entire_msg + "\n" + np_msg #<<<<<
                continue

    if (not got_rv) or (not got_op) or (not got_np):
        entire_msg = entire_msg + "\n" + ERROR_MSG  # <<<<<
    else:
        if (len(label) == 2):
            entire_msg = entire_msg + label[0] + ": " + apply_unit(rv.cum_this_qtr, unit) + " / " + apply_unit(
                op.cum_this_qtr, unit) + " / " + apply_unit(np.cum_this_qtr, unit) + "\n"
            entire_msg = entire_msg + label[1] + ": " + apply_unit(rv.cum_this_qtr_prev_yr, unit) + " / " + apply_unit(
                op.cum_this_qtr_prev_yr, unit) + " / " + apply_unit(np.cum_this_qtr_prev_yr, unit) + "\n"
            entire_msg = entire_msg + "증감비율(%): " + rv.yoy + " / " + op.yoy + " / " + np.yoy + "\n"
        else:
            entire_msg = entire_msg + "\n" + ERROR_MSG  # <<<<<

    entire_msg = entire_msg + "증감사유: " + reason_msg + "\n\n공시링크: " + report_link
    send_tele_msg(entire_msg)
    return EarningData(report_date, report_type, report_name, report_link, company_name, stock_code, unit, label, rv,
                       op, np, cnp)


def get_account_data(tr_list: list, idx: int):
    td0_list = tr_list[idx].find_elements(by=By.TAG_NAME, value='td')
    this_qtr = fix_bracket_for_number(clean_blank(td0_list[2].text))
    prev_qtr = fix_bracket_for_number(clean_blank(td0_list[3].text))
    this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td0_list[5].text))
    this_qoq = fix_bracket_for_number(clean_blank(td0_list[4].text))
    this_yoy = fix_bracket_for_number(clean_blank(td0_list[6].text))

    td1_list = tr_list[idx + 1].find_elements(by=By.TAG_NAME, value='td')
    cum_this_qtr = fix_bracket_for_number(clean_blank(td1_list[1].text))
    cum_prev_qtr = fix_bracket_for_number(clean_blank(td1_list[2].text))
    cum_this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td1_list[4].text))
    # cum_qoq = fix_bracket_for_number(clean_blank(td1_list[4].text))
    # cum_yoy = fix_bracket_for_number(clean_blank(td1_list[6].text))

    return [this_qtr, prev_qtr, this_qtr_prev_yr, cum_this_qtr, cum_prev_qtr, cum_this_qtr_prev_yr, this_qoq, this_yoy]


def parser_provisional_earning(report: Report, market_cap: int, stock_code: str):
    report_date = report.rcept_dt
    report_type = "개별"
    report_name = report.report_nm
    report_link = "https://dart.fss.or.kr" + report.report_link
    company_name = report.corp_name
    unit = None
    label = []
    rv = Account(False, None, None, None, None, None, None, None, None, None)
    op = Account(False, None, None, None, None, None, None, None, None, None)
    np = Account(False, None, None, None, None, None, None, None, None, None)
    cnp = Account(False, None, None, None, None, None, None, None, None, None)

    # print()
    # print("corp_name: ", company_name)
    # print("report_name: ", report_name)
    # print("report_link: ", report_link)

    if report.report_nm.find("연결") != -1:
        report_type = "연결"
    # print("report_type: ", report_type)

    market_cap_str = add_comma(str(int(market_cap / 1e8))) + '억'
    entire_msg = datetime.now().strftime("%Y.%m.%d %H:%M:%S") + "\n" + \
                 "기업명: " + company_name + "(시가총액: " + market_cap_str + ")\n" + \
                 "공시일: " + report_date + "\n" + \
                 "보고서명: " + report_name + "\n\n"

    tr_list = get_xml_from_link(report_link)

    got_unit = got_label = False
    got_rv = got_op = got_np = got_cnp = got_reason = False

    for i, tr in enumerate(tr_list):
        # find unit: 원/천원/백만원/억원/조원
        if (not got_unit):
            found_unit = (tr.text.find("단위") != -1) and (tr.text.find("원") != -1)
            if found_unit:
                unit = find_unit(tr.text)
                got_unit = True
                # unit_msg = "unit: " + str(unit)
                # print(unit_msg)
                # entire_msg = entire_msg + "\n" + unit_msg #<<<<<
        # find label
        if (not got_label):
            found_label = tr.text.find("구분") != -1
            if found_label:
                td_list = tr_list[i + 1].find_elements(by=By.TAG_NAME, value='td')
                label.append(clean_string(td_list[0].text))
                label.append(clean_string(td_list[1].text))
                label.append(clean_string(td_list[2].text))
                got_label = True
                # label_msg = "label: " + ', '.join(label)
                # print(label_msg)
                # entire_msg = entire_msg + "\n" + label_msg #<<<<<
        # find revenue
        if (got_unit and got_label) and (not got_rv):
            found_rv = tr.text.find("매출액") != -1
            if found_rv:
                rv.exist = found_rv

                [rv.this_qtr, rv.prev_qtr, rv.this_qtr_prev_yr, rv.cum_this_qtr, rv.cum_prev_qtr,
                 rv.cum_this_qtr_prev_yr, rv.qoq, rv.yoy] = get_account_data(tr_list, i)
                got_rv = True
                # rv_msg1 = 'rv ths: [' + rv.this_qtr + ', ' + rv.prev_qtr + ', ' + rv.this_qtr_prev_yr + ']'
                # print(rv_msg1)
                # rv_msg2 = 'rv cum: [' + rv.cum_this_qtr + ', ' + rv.cum_prev_qtr + ', ' + rv.cum_this_qtr_prev_yr + ']'
                # print(rv_msg2)
                # entire_msg = entire_msg + "\n" + rv_msg1 + "\n" + rv_msg2 #<<<<<
                continue
        # find operating profit
        if (got_unit and got_label and got_rv) and (not got_op):
            found_op = tr.text.find("영업이익") != -1
            if found_op:
                op.exist = found_op
                [op.this_qtr, op.prev_qtr, op.this_qtr_prev_yr, op.cum_this_qtr, op.cum_prev_qtr,
                 op.cum_this_qtr_prev_yr, op.qoq, op.yoy] = get_account_data(tr_list, i)
                got_op = True
                # op_msg1 = 'op ths: [' + op.this_qtr + ', ' + op.prev_qtr + ', ' + op.this_qtr_prev_yr + ']'
                # print(op_msg1)
                # op_msg2 = 'op cum: [' + op.cum_this_qtr + ', ' + op.cum_prev_qtr + ', ' + op.cum_this_qtr_prev_yr + ']'
                # print(op_msg2)
                # entire_msg = entire_msg + "\n" + op_msg1 + "\n" + op_msg2 #<<<<<
                continue
        # find net profit
        if (got_unit and got_label and got_rv and got_op) and (not got_np):
            found_np = tr.text.find("당기순이익") != -1
            if found_np:
                np.exist = found_np
                [np.this_qtr, np.prev_qtr, np.this_qtr_prev_yr, np.cum_this_qtr, np.cum_prev_qtr,
                 np.cum_this_qtr_prev_yr, np.qoq, np.yoy] = get_account_data(tr_list, i)
                got_np = True
                # np_msg1 = 'np ths: [' + np.this_qtr + ', ' + np.prev_qtr + ', ' + np.this_qtr_prev_yr + ']'
                # print(np_msg1)
                # np_msg2 = 'np cum: [' + np.cum_this_qtr + ', ' + np.cum_prev_qtr + ', ' + np.cum_this_qtr_prev_yr + ']'
                # print(np_msg2)
                # entire_msg = entire_msg + "\n" + np_msg1 + "\n" + np_msg2 #<<<<<
                continue
        # find controlling net profit
        if (got_unit and got_label and got_rv and got_op and got_np) and (not got_cnp):
            found_cnp = tr.text.find("지배기업 소유주지분 순이익") != -1
            if found_cnp:
                cnp.exist = found_cnp
                [cnp.this_qtr, cnp.prev_qtr, cnp.this_qtr_prev_yr, cnp.cum_this_qtr, cnp.cum_prev_qtr,
                 cnp.cum_this_qtr_prev_yr, cnp.qoq, cnp.yoy] = get_account_data(tr_list, i)
                got_cnp = True
                # cnp_msg1 = 'cnp ths: [' + cnp.this_qtr + ', ' + cnp.prev_qtr + ', ' + cnp.this_qtr_prev_yr + ']'
                # print(cnp_msg1)
                # cnp_msg2 = 'cnp cum: [' + cnp.cum_this_qtr + ', ' + cnp.cum_prev_qtr + ', ' + cnp.cum_this_qtr_prev_yr + ']'
                # print(cnp_msg2)
                # entire_msg = entire_msg + "\n" + cnp_msg1 + "\n" + cnp_msg2 #<<<<<
                continue
    if (not got_rv) or (not got_op) or (not got_np):
        entire_msg = entire_msg + "\n" + ERROR_MSG  # <<<<<
    else:
        if (len(label) == 3):
            entire_msg = entire_msg + label[0] + " " + apply_unit(rv.this_qtr, unit) + " / " + apply_unit(op.this_qtr,
                                                                                                          unit) + " / " + apply_unit(
                np.this_qtr, unit) + "\n"
            entire_msg = entire_msg + label[1] + " " + apply_unit(rv.prev_qtr, unit) + " / " + apply_unit(op.prev_qtr,
                                                                                                          unit) + " / " + apply_unit(
                np.prev_qtr, unit) + "\n"
            entire_msg = entire_msg + label[2] + " " + apply_unit(rv.this_qtr_prev_yr, unit) + " / " + apply_unit(
                op.this_qtr_prev_yr, unit) + " / " + apply_unit(np.this_qtr_prev_yr, unit) + "\n"
            entire_msg = entire_msg + "QoQ(%): " + rv.qoq + " / " + op.qoq + " / " + np.qoq + "\n"
            entire_msg = entire_msg + "YoY(%): " + rv.yoy + " / " + op.yoy + " / " + np.yoy + "\n"
        else:
            entire_msg = entire_msg + "\n" + ERROR_MSG  # <<<<<

    entire_msg = entire_msg + "\n공시링크: " + report_link
    send_tele_msg(entire_msg)
    return EarningData(report_date, report_type, report_name, report_link, company_name, stock_code, unit, label, rv,
                       op, np, cnp)

def findReport(corp_code:str, bsns_year:str, reprt_code:str, report_num:str):
    reportFound = None
    try:
        reportFound = dart_fss.api.finance.fnltt_singl_acnt(corp_code=corp_code, bsns_year=bsns_year, reprt_code=reprt_code)
        if ((len(reportFound) > 0) and (len(reportFound['list']) > 0) and (reportFound['list'][0]['rcept_no'] == report_num)):
            found = True
    except:
        found = False

    return found, reportFound

def parser_quaterly_report(report: Report, market_cap: int, stock_code: str, corp_code: str):
    report_date = report.rcept_dt
    report_type = ""
    report_name = report.report_nm
    report_link = "https://dart.fss.or.kr" + report.report_link
    report_num = report_link.split('=')[1]
    company_name = report.corp_name
    stock_code = stock_code
    unit = None
    label = []
    rv = Account(False, None, None, None, None, None, None, None, None, None)
    op = Account(False, None, None, None, None, None, None, None, None, None)
    np = Account(False, None, None, None, None, None, None, None, None, None)
    cnp = Account(False, None, None, None, None, None, None, None, None, None)

    # 보고서에서 재무데이터 가져오기
    # TODO: 회사에따라 bsns_year 달라질수 있음 -> 처리방안 필요(몇월 결산법인인지 확인후 bsns_year 설정)
    bsns_year = '2022'
    if(report.report_nm.find('사업')!=-1):
        result = findReport(corp_code, bsns_year, '11011', report_num)
    elif(report.report_nm.find('반기')!=-1):
        result = findReport(corp_code, bsns_year, '11012', report_num)
    else: # 분기보고서: 1분기/3분기 중 하나
        result = findReport(corp_code, bsns_year, '11013', report_num)
        if(result[0] == False):
            result = findReport(corp_code, bsns_year, '11014', report_num)
    found = result[0] # 보고서 재무데이터 찾았는지 여부
    reportFound = result[1] # 찾은경우: 보고서 재무데이터, 못찾은경우: None, pd.DataFrame(reportFound['list'])
    # TODO: 요약재무 크롤링 vs 위 결과 사용 중 쉬운걸로 작업 (위 방법은 실시간으로 api에서 결과가 대부분 제공된다는 전제가 필요 -> 검증필요)

    market_cap_str = add_comma(str(int(market_cap / 1e8))) + '억'
    if(found==True):
        foundText = "True"
    else:
        # TODO: 보고서에서 실적수치 추출
        foundText = "True"
    entire_msg = datetime.now().strftime("%Y.%m.%d %H:%M:%S") + "\n" + \
                 "기업명: " + company_name + "(시가총액: " + market_cap_str + ")\n" + \
                 "공시일: " + report_date + "\n" + \
                 "보고서명: " + report_name + "\n" + \
                 "보고서존재: " + foundText + "\n" + \
                 "공시링크: " + report_link

    send_tele_msg(entire_msg)
    return EarningData(report_date, report_type, report_name, report_link, company_name, stock_code, unit, label, rv,
                       op, np, cnp)


if __name__ == '__main__':
    import sys
    # overshooting_list('2022-02-25', '2022-02-25')
    # print(overshooting_show('/dsaf001/main.do?rcpNo=20220225901625'))
