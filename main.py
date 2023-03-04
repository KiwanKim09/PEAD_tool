'''
import OpenDartReader

api_key='4963d6ec90d0c9ec140c1fe9f5b2a325dd734b9f'
dart = OpenDartReader(api_key)

dart.set_api_key(api_key=api_key)

dart.list(None, start=None, end=None, kind='', kind_detail='', final=True)

'''
from optparse import Option
import re
import os
from datetime import datetime

import OpenDartReader
import dart_fss
import time
import requests
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

__TOKEN = "5948138313:AAF4lys6I8vcghJ-h6fHYXQcRPh86TiafUI"
__chat_id = -1001820286028
ERROR_MSG = "*** (ERROR) 파싱 오류 ***"

class Account:
    
    def __init__(self, exist: bool, this_qtr: str, prev_qtr: str, this_qtr_prev_yr: str, cum_this_qtr: str, cum_prev_qtr: str, cum_this_qtr_prev_yr: str):
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
        self.this_qtr = this_qtr # this_qtr_data
        self.prev_qtr = prev_qtr # right_before_qtr_data
        self.this_qtr_prev_yr = this_qtr_prev_yr # prev_yr_same_qtr_data
        
        self.cum_this_qtr = cum_this_qtr # this_qtr_cumulative_data
        self.cum_prev_qtr = cum_prev_qtr # right_before_qtr_cumalative_data
        self.cum_this_qtr_prev_yr = cum_this_qtr_prev_yr # prev_yr_same_qtr_cumalative_data

    def __str__(self) -> str:
        return f'Account(exist={self.exist}, this_qtr={self.this_qtr}, prev_qtr={self.prev_qtr}, this_qtr_prev_yr={self.this_qtr_prev_yr}, cum_this_qtr={self.cum_this_qtr}, cum_prev_qtr={self.cum_prev_qtr}, cum_this_qtr_prev_yr={self.cum_this_qtr_prev_yr})\n'
    
class EarningData:
    
    def __init__(self, report_date: str, report_type: str, report_name: str, report_link: str, company_name: str, stock_code: str, unit: int, label: list, rv: Account, op: Account, np: Account, cnp: Account):
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


def add_comma(origin_str: str):

    temp_str = ''
    if(origin_str[0]=='-'):
        temp_str = origin_str[0]
        origin_str = origin_str.replace('-','')

    if (len(origin_str) >= 4):
        s1 = origin_str[0:len(origin_str) - 3]
        s2 = origin_str[len(origin_str) - 3:len(origin_str)]
        s1 = add_comma(s1)
        return temp_str+s1+","+s2
    else:
        return temp_str+origin_str

def apply_unit(value_str: str, unit: int):
    if(value_str=='-'):
        return value_str

    try:
        value = int(value_str.replace(',','')) * unit
    except:
        value = int(value_str.replace('.', '')) * unit
    eok = int(value/1e8)

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
    options = webdriver.ChromeOptions()
    options.add_argument('disable-gpu')    # GPU 사용 안함
    options.add_argument('lang=ko_KR')    # 언어 설정
    options.add_experimental_option('excludeSwitches', ['enable-logging'])    # 로그 출력 안함
    os.environ['WDM_LOG_LEVEL'] = '0'
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), chrome_options=options)
    driver.get(report_link)
    try:
        element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'viewWrap'))
		)  # 웹 브라우저가 정상적으로 로딩될 때까지 기다림
        iframe = driver.find_element(by=By.TAG_NAME, value='iframe')
        driver.switch_to.frame(iframe)
        tr_list = driver.find_elements(by=By.TAG_NAME, value='tr')
        return tr_list
    except TimeoutException:
        print('타임아웃: ', link)
    return

def parser_30pcnt_change(report: Report):
    xml_text = open_dart.document(report.rcp_no)
    #print(xml_text)
    
    soup = BeautifulSoup(xml_text, 'lxml')
    tr_list = soup.find('tbody').find_all('tr')
    
    report_date = report.rcept_dt
    report_type = None
    report_name = report.report_nm
    report_link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + report.rcp_no
    company_name = report.corp_name
    stock_code = report.stock_code
    unit = None
    label = []
    rv = Account(False, None, None, None, None, None, None)
    op = Account(False, None, None, None, None, None, None)
    np = Account(False, None, None, None, None, None, None)
    cnp = Account(False, None, None, None, None, None, None)
    
    '''
    print()
    print("corp_name: ", company_name)
    print("report_name: ", report_name)
    print("report_link: ", report_link)
    '''

    market_cap = stock.get_market_cap("20230224").loc[report.stock_code]['시가총액'] # 하루 한번만 콜해서 전일종가 쓰는게 나을듯
    market_cap_str = add_comma(str(int(market_cap / 1e8))) + '억'
    entire_msg = datetime.now().strftime("%Y.%m.%d %H:%M:%S") + "\n" + \
                 "기업명: " + company_name + "(시가총액: " + market_cap_str + ")\n" + \
                 "보고서명: " + report_name
    
    got_type = got_unit = got_label = False
    got_rv = got_op = got_np = got_cnp = False
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
                type_msg = "개별/연결: " + report_type
                #print(type_msg)
                entire_msg = entire_msg + "\n" + type_msg + "\n\n" #<<<<<
        # find unit: 원/천원/백만원/억원/조원
        if (not got_unit):
            found_unit = (tr.text.find("단위") != -1) and (tr.text.find("원") != -1)
            if found_unit:
                unit = find_unit(tr.text)
                got_unit = True
                # unit_msg = "단위: " + add_comma(str(unit))
                #print(unit_msg)
                # entire_msg = entire_msg + "\n" + unit_msg + "\n\n" #<<<<<
        # find label
        if (not got_label):
            found_label = tr.text.find("2. 매출액 또는 손익구조") != -1
            if found_label:
                td_list = tr.find_all('td')
                label.append(clean_string(td_list[1].text))
                label.append(clean_string(td_list[2].text))
                got_label = True
                # label_msg = "label: " + ', '.join(label)
                #print(label_msg)
                # entire_msg = entire_msg + "\n" + label_msg #<<<<<
                continue
        # find revenue
        if (got_type and got_unit and got_label) and (not got_rv):
            found_rv = tr.text.find("- 매출액") != -1
            if found_rv:
                td_list = tr.find_all('td')
                rv.exist = found_rv
                rv.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list[1].text))
                rv.cum_this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td_list[2].text))
                got_rv = True
                rv_msg = 'rv: [' + rv.cum_this_qtr + ', ' + rv.cum_this_qtr_prev_yr + ']'
                #print(rv_msg)
                # entire_msg = entire_msg + "\n" + rv_msg #<<<<<
                continue
        # find operating profit
        if (got_type and got_unit and got_label and got_rv) and (not got_op):
            found_op = tr.text.find("- 영업이익") != -1
            if found_op:
                td_list = tr.find_all('td')
                op.exist = found_op
                op.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list[1].text))
                op.cum_this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td_list[2].text))
                got_op = True
                op_msg = 'op: [' + op.cum_this_qtr + ', ' + op.cum_this_qtr_prev_yr + ']'
                #print(op_msg)
                # entire_msg = entire_msg + "\n" + op_msg #<<<<<
                continue
        # find net profit
        if (got_type and got_unit and got_label and got_rv and got_op) and (not got_np):
            found_np = tr.text.find("- 당기순이익") != -1
            if found_np:
                td_list = tr.find_all('td')
                np.exist = found_np
                np.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list[1].text))
                np.cum_this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td_list[2].text))
                got_np = True
                np_msg = 'np: [' + np.cum_this_qtr + ', ' + np.cum_this_qtr_prev_yr + ']'
                #print(np_msg)
                # entire_msg = entire_msg + "\n" + np_msg #<<<<<
                continue
    if (not got_rv) or (not got_op) or (not got_np):
        entire_msg = entire_msg + "\n" + ERROR_MSG #<<<<<
    else:
        if(len(label) == 2):
            entire_msg = entire_msg + label[0] + " " + apply_unit(rv.cum_this_qtr,unit) + " / " + apply_unit(op.cum_this_qtr,unit) + " / " + apply_unit(np.cum_this_qtr,unit) + "\n"
            entire_msg = entire_msg + label[1] + " " + apply_unit(rv.cum_this_qtr_prev_yr,unit) + " / " + apply_unit(op.cum_this_qtr_prev_yr,unit) + " / " + apply_unit(np.cum_this_qtr_prev_yr,unit)
        else:
            entire_msg = entire_msg + "\n" + ERROR_MSG  # <<<<<

    entire_msg = entire_msg + "\n\n공시링크: " + report_link

    send_tele_msg(entire_msg)
    return EarningData(report_date, report_type, report_name, report_link, company_name, stock_code, unit, label, rv, op, np, cnp)

def get_account_data(tr_list: list, idx: int):
    td0_list = tr_list[idx].find_all('td')
    this_qtr = fix_bracket_for_number(clean_blank(td0_list[2].text))
    prev_qtr = fix_bracket_for_number(clean_blank(td0_list[3].text))
    this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td0_list[5].text))
    
    td1_list = tr_list[idx+1].find_all('td')
    cum_this_qtr = fix_bracket_for_number(clean_blank(td1_list[1].text))
    cum_prev_qtr = fix_bracket_for_number(clean_blank(td1_list[2].text))
    cum_this_qtr_prev_yr = fix_bracket_for_number(clean_blank(td1_list[4].text))
    
    return [this_qtr, prev_qtr, this_qtr_prev_yr, cum_this_qtr, cum_prev_qtr, cum_this_qtr_prev_yr]

def parser_provisional_earning(report: Report):
    xml_text = open_dart.document(report.rcp_no)
    soup = BeautifulSoup(xml_text, 'lxml')
    tr_list = soup.find('tbody').find_all('tr')
    
    report_date = report.rcept_dt
    report_type = "개별"
    report_name = report.report_nm
    report_link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + report.rcp_no
    company_name = report.corp_name
    stock_code = report.stock_code
    unit = None
    label = []
    rv = Account(False, None, None, None, None, None, None)
    op = Account(False, None, None, None, None, None, None)
    np = Account(False, None, None, None, None, None, None)
    cnp = Account(False, None, None, None, None, None, None)
    
    # test start vvvv
    #get_xml_from_link(report_link)
    # test end ^^^^^^
    
    '''
    print()
    print("corp_name: ", company_name)
    print("report_name: ", report_name)
    print("report_link: ", report_link)
    '''
    
    if report.report_nm.find("연결") != -1:
        report_type = "연결"
    #print("report_type: ", report_type)

    market_cap = stock.get_market_cap("20230224").loc[report.stock_code]['시가총액']
    market_cap_str = add_comma(str(int(market_cap / 1e8))) + '억'
    entire_msg = datetime.now().strftime("%Y.%m.%d %H:%M:%S") + "\n" + \
                 "기업명: " + company_name + "(시가총액: " + market_cap_str + ")\n" + \
                 "보고서명: " + report_name + "\n\n"

    got_unit = got_label = False
    got_rv = got_op = got_np = got_cnp = False;
    
    for i, tr in enumerate(tr_list):
        # find unit: 원/천원/백만원/억원/조원
        if (not got_unit):
            found_unit = (tr.text.find("단위") != -1) and (tr.text.find("원") != -1)
            if found_unit:
                unit = find_unit(tr.text)
                got_unit = True
                # unit_msg = "단위: " + add_comma(str(unit))
                #print(unit_msg)
                # entire_msg = entire_msg + "\n" + unit_msg + "\n\n" #<<<<<
        # find label
        if (not got_label):
            found_label = tr.text.find("구분") != -1
            if found_label:
                td_list = tr_list[i+1].find_all('td')
                label.append(clean_string(td_list[0].text))
                label.append(clean_string(td_list[1].text))
                label.append(clean_string(td_list[2].text))
                got_label = True
                # label_msg = "label: " + ', '.join(label)
                #print(label_msg)
                # entire_msg = entire_msg + "\n" + label_msg #<<<<<
        # find revenue
        if (got_unit and got_label) and (not got_rv):
            found_rv = tr.text.find("매출액") != -1
            if found_rv:
                rv.exist = found_rv
                [rv.this_qtr, rv.prev_qtr, rv.this_qtr_prev_yr, rv.cum_this_qtr, rv.cum_prev_qtr, rv.cum_this_qtr_prev_yr] = get_account_data(tr_list, i)
                got_rv = True
                rv_msg1 = 'rv ths: [' + rv.this_qtr + ', ' + rv.prev_qtr + ', ' + rv.this_qtr_prev_yr + ']'
                #print(rv_msg1)
                rv_msg2 = 'rv cum: [' + rv.cum_this_qtr + ', ' + rv.cum_prev_qtr + ', ' + rv.cum_this_qtr_prev_yr + ']'
                #print(rv_msg2)
                # entire_msg = entire_msg + "\n" + rv_msg1 + "\n" + rv_msg2 #<<<<<
                continue
        # find operating profit
        if (got_unit and got_label and got_rv) and (not got_op):
            found_op = tr.text.find("영업이익") != -1
            if found_op:
                op.exist = found_op
                [op.this_qtr, op.prev_qtr, op.this_qtr_prev_yr, op.cum_this_qtr, op.cum_prev_qtr, op.cum_this_qtr_prev_yr] = get_account_data(tr_list, i)
                got_op = True
                op_msg1 = 'op ths: [' + op.this_qtr + ', ' + op.prev_qtr + ', ' + op.this_qtr_prev_yr + ']'
                #print(op_msg1)
                op_msg2 = 'op cum: [' + op.cum_this_qtr + ', ' + op.cum_prev_qtr + ', ' + op.cum_this_qtr_prev_yr + ']'
                #print(op_msg2)
                # entire_msg = entire_msg + "\n" + op_msg1 + "\n" + op_msg2 #<<<<<
                continue
        # find net profit
        if (got_unit and got_label and got_rv and got_op) and (not got_np):
            found_np = tr.text.find("당기순이익") != -1
            if found_np:
                np.exist = found_np
                [np.this_qtr, np.prev_qtr, np.this_qtr_prev_yr, np.cum_this_qtr, np.cum_prev_qtr, np.cum_this_qtr_prev_yr] = get_account_data(tr_list, i)
                got_np = True
                np_msg1 = 'np ths: [' + np.this_qtr + ', ' + np.prev_qtr + ', ' + np.this_qtr_prev_yr + ']'
                #print(np_msg1)
                np_msg2 = 'np cum: [' + np.cum_this_qtr + ', ' + np.cum_prev_qtr + ', ' + np.cum_this_qtr_prev_yr + ']'
                #print(np_msg2)
                # entire_msg = entire_msg + "\n" + np_msg1 + "\n" + np_msg2 #<<<<<
                continue
        # find controlling net profit
        if (got_unit and got_label and got_rv and got_op and got_np) and (not got_cnp):
            found_cnp = tr.text.find("지배기업 소유주지분 순이익") != -1
            if found_cnp:
                cnp.exist = found_cnp
                [cnp.this_qtr, cnp.prev_qtr, cnp.this_qtr_prev_yr, cnp.cum_this_qtr, cnp.cum_prev_qtr, cnp.cum_this_qtr_prev_yr] = get_account_data(tr_list, i)
                got_cnp = True
                cnp_msg1 = 'cnp ths: [' + cnp.this_qtr + ', ' + cnp.prev_qtr + ', ' + cnp.this_qtr_prev_yr + ']'
                #print(cnp_msg1)
                cnp_msg2 = 'cnp cum: [' + cnp.cum_this_qtr + ', ' + cnp.cum_prev_qtr + ', ' + cnp.cum_this_qtr_prev_yr + ']'
                #print(cnp_msg2)
                # entire_msg = entire_msg + "\n" + cnp_msg1 + "\n" + cnp_msg2 #<<<<<
                continue
    if (not got_rv) or (not got_op) or (not got_np):
        entire_msg = entire_msg + "\n" + ERROR_MSG #<<<<<
    else:
        if(len(label) == 3):
            entire_msg = entire_msg + label[0] + " " + apply_unit(rv.this_qtr, unit) + " / " + apply_unit(op.this_qtr, unit) + " / " + apply_unit(np.this_qtr, unit) + "\n"
            entire_msg = entire_msg + label[1] + " " + apply_unit(rv.prev_qtr, unit) + " / " + apply_unit(op.prev_qtr, unit) + " / " + apply_unit(np.prev_qtr, unit) + "\n"
            entire_msg = entire_msg + label[2] + " " + apply_unit(rv.this_qtr_prev_yr, unit) + " / " + apply_unit(op.this_qtr_prev_yr, unit) + " / " + apply_unit(np.this_qtr_prev_yr, unit)
        else:
            entire_msg = entire_msg + "\n" + ERROR_MSG  # <<<<<

    entire_msg = entire_msg + "\n\n공시링크: " + report_link
    send_tele_msg(entire_msg)
    return EarningData(report_date, report_type, report_name, report_link, company_name, stock_code, unit, label, rv, op, np, cnp)

def parser_quaterly_report(report:Report):
    report_date = report.rcept_dt
    report_type = "개별"
    report_name = "정기보고서"
    report_link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + report.rcp_no
    company_name = report.corp_name
    stock_code = report.stock_code
    unit = None
    label = []
    rv = Account(False, None, None, None, None, None, None)
    op = Account(False, None, None, None, None, None, None)
    np = Account(False, None, None, None, None, None, None)
    cnp = Account(False, None, None, None, None, None, None)
    '''
    print()
    print("corp_name: ", company_name)
    print("report_name: ", report_name)
    print("report_link: ", report_link)
    '''
    entire_msg = company_name + "\n" + report_name + "\n" + report_link

    # find summerized finance info xml
    xml_text = open_dart.document(report.rcp_no)
    marker_start='1. 요약재무정보'
    marker_end='2. 연결재무제표'
    # print(xml_text)
    summerized_xml = xml_text.partition(marker_start)[2].partition(marker_end)[0]
    #print("XML: ", summerized_xml)
    soup = BeautifulSoup(summerized_xml, 'html.parser')
    #print("SOUP: ", soup)
    
    got_type = got_unit = got_label = False
    got_rv = got_op = got_np = got_cnp = False
    # thead parsing
    thead_list = soup.find_all('thead')
    #print("Thead: ", thead_list)
    #print("thead size:", len(thead_list))
    for thead in thead_list:
        # find label
        if (not got_label):
            thead_clean = clean_blank(thead.text)
            found_label = thead_clean.find("과목") != -1 or \
                          thead_clean.find("구분") != -1 or \
                          (thead_clean.find('제') != -1 and thead_clean.find('기') != -1)
            if found_label:
                hd_list = thead.find_all('th')
                label.append(clean_string(hd_list[1].text))
                got_label = True
                label_msg = "label: " + label
                #print(label_msg)
                entire_msg = entire_msg + "\n" + label_msg #<<<<<
        else:
            continue
    # tbody parsing
    tb_list = soup.find_all('tbody')
    report_type = "개별"
    for tb in tb_list:
        # find type: 연결/개별
        if (not got_type):
            found_type_cons = tb.text.find("연결") != -1 or \
                              len(thead_list) == 2
            if found_type_cons:
                report_type = "연결"
                got_type = True
                type_msgs = "report_type: " + report_type
                #print(type_msgs)
                entire_msg = entire_msg + "\n" + type_msgs #<<<<<
        # find unit: 원/천원/백만원/억원/조원
        if (not got_unit):
            tb_clean = clean_blank(tb.text)
            found_unit = (tb_clean.find("단위") != -1) and (tb_clean.find("원") != -1)
            if found_unit:
                unit = find_unit(tb.text)
                got_unit = True
                unit_msgs = "unit: " + unit
                #print(unit_msgs)
                entire_msg = entire_msg + "\n" + unit_msgs #<<<<<
        # unit 찾으면, tbody loop에서 tr loop로 촘촘히 스캔
        if got_unit:
            tr_list = tb.find_all('tr')
            for i, tr in enumerate(tr_list):
                # find revenue
                if (got_unit and got_label) and (not got_rv): # type은 체크하면 안 됨
                    tr_clean = clean_blank(tr.text)
                    found_rv = tr_clean.find("매출") != -1 or \
                               tr_clean.find("영업수익") != -1
                    if found_rv:
                        rv.exist = found_rv
                        td_list = tr.find_all('td')
                        rv.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list[1].text))
                        got_rv = True
                        #print("* cum rv: ", rv.cum_this_qtr)
                        continue
                # find op
                if (got_unit and got_label and got_rv) and (not got_op):
                    tr_clean = clean_blank(tr.text)
                    found_op = tr_clean.find("영업이익") != -1 or \
                               tr_clean.find("영업손실") != -1
                    if found_op:
                        op.exist = found_rv
                        td_list = tr.find_all('td')
                        op.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list[1].text))
                        got_op = True
                        #print("* cum op: ", op.cum_this_qtr)
                        continue
                # find np
                if (got_unit and got_label and got_rv and got_op) and (not got_np):
                    tr_clean = clean_blank(tr.text)
                    found_np = tr_clean.find("당기순이익") != -1 or \
                               tr_clean.find("당기순순실") != -1 or \
                               tr_clean.find("반기순이익") != -1 or \
                               tr_clean.find("반기순순실") != -1 or \
                               tr_clean.find("분기순이익") != -1 or \
                               tr_clean.find("분기순순실") != -1
                    if found_np:
                        np.exist = found_rv
                        td_list = tr.find_all('td')
                        np.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list[1].text))
                        got_np = True
                        #print("* cum np: ", np.cum_this_qtr)
                        
                        # find cnp
                        tr_next = tr_list[i+1]
                        tr_next_clean = clean_blank(tr_next.text)
                        found_cnp = tr_next_clean.find("지배") != -1 and \
                                    tr_next_clean.find("비지배") == -1
                        if found_cnp:
                            cnp.exist = found_cnp
                            td_list2 = tr_next.find_all('td')
                            cnp.cum_this_qtr = fix_bracket_for_number(clean_blank(td_list2[1].text))
                            got_cnp = True
                            #print("* cum cnp: ", cnp.cum_this_qtr)
                        continue
    '''
    # error detection
    if (not got_rv) or (not got_op) or (not got_np):
        print('***** 못찾음, 이상함 *****')
        print("rv, op, np: ", got_rv, ", ", got_op, ", ", got_np)
    '''
    if (got_rv and got_op and got_np):
        send_tele_msg(entire_msg)
    return EarningData(report_date, report_type, report_name, report_link, company_name, stock_code, unit, label, rv, op, np, cnp)

kw_auth = '4963d6ec90d0c9ec140c1fe9f5b2a325dd734b9f'
cw_auth = 'dd10e1670e0342047b917ac6de571c0b631d1aff'
dart_fss.set_api_key(cw_auth)
open_dart = OpenDartReader(cw_auth)

start_date = '20230206'
end_date = '20230206'
page_cnt = 100 # 한 페이지에 문서 갯수
page = 1
running = True
earning_reports=[]
while running:
    reports = dart_fss.filings.search(corp_code=None, 
                                      bgn_de = start_date, 
                                      end_de = end_date, 
                                      last_reprt_at = 'N', 
                                      pblntf_ty = None, 
                                      pblntf_detail_ty = ['A001', 'A002', 'A003', 'I001', 'I002'],
                                      corp_cls = None,
                                      sort = 'date', 
                                      sort_mth = 'desc', 
                                      page_no = page, 
                                      page_count = page_cnt)
    running = page < reports.total_page
    #print("page numb: ", page, " / ", reports.total_page)
    for report in reports.report_list:
        # 코스피, 코스닥 필터링
        is_no_kospi = report.corp_cls.find("Y") == -1
        is_no_Kosdaq = report.corp_cls.find("K") == -1
        if is_no_kospi and is_no_Kosdaq:
            #print(report.corp_name, "-pass: no kospi/kosdaq")
            continue
        
        # 변동, 잠정, 보고서 필터링
        is_no_30pcnt_change = report.report_nm.find("30%") == -1
        is_no_provisional_report = report.report_nm.find("잠정") == -1
        is_no_annual_report = report.report_nm.find("사업보고서") == -1
        is_no_half_report = report.report_nm.find("반기보고서") == -1
        is_no_quarter_report = report.report_nm.find("분기보고서") == -1
        if is_no_30pcnt_change and is_no_provisional_report and is_no_annual_report and is_no_half_report and is_no_quarter_report: 
            #print(report.corp_name, "-pass: no earning report")
            continue
        
        # 정정, 월별, 자회사, 연장 필터링    
        is_correction = report.report_nm.find("정정") != -1
        is_monthly = report.report_nm.find("월별") != -1
        is_subsidiary = report.report_nm.find("자회사") != -1
        is_extension = report.report_nm.find("연장") != -1
        if is_correction or is_monthly or is_subsidiary or is_extension:
            #print(report.corp_name, "-pass: 정정/월별/자회사 report")
            continue
        
        # 스팩 필터링
        is_spac = report.corp_name.find("스팩") != -1
        if is_spac:
            continue
        
        '''
        # test filter
        if is_no_annual_report and is_no_half_report and is_no_quarter_report: 
            continue
        '''
        
        earning_reports.append(report)
    
    page = page + 1
    time.sleep(0.01)

'''
print()    
print(earning_reports)
print()
'''

earning_data_list=[]
for report in earning_reports:
    is_periodic_report = (report.report_nm.find("사업보고서") != -1) or \
                         (report.report_nm.find("반기보고서") != -1) or \
                         (report.report_nm.find("분기보고서") != -1)
    
    if report.report_nm.find("잠정") != -1:
        #continue # test <<<<<
        # template.1 - 영업(잠정)실적(공정공시)
        # ('11013'=1분기보고서, '11012'=반기보고서, '11014'=3분기보고서, '11011'=사업보고서)
        # ('CFS'=연결제무제표, 'OFS'=별도(개별)제무제표)

        earning_data = parser_provisional_earning(report)
        # print(earning_data)
        # earning_data_list.append(earning_data)
    elif report.report_nm.find("30%") != -1:
        #continue # test <<<<<
        # template.2 - 매출액또는손익구조30%(대규모법인은15%)이상변경
        earning_data = parser_30pcnt_change(report)
        #print(earning_data)
        # earning_data_list.append(earning_data)
    # elif report.report_nm.find("보고서") != -1:
    #     # template.3 - 사업/반기/분기 보고서
    #     earning_data = parser_quaterly_report(report)
    #     earning_data_list.append(earning_data)
    #     #break
    
    time.sleep(0.06)


