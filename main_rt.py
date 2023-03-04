from dart.dart import get_disclosure, parser_provisional_earning, parser_30pcnt_change, parser_quaterly_report
import dart_fss
from pykrx import stock
import time
import datetime
from tqdm import tqdm
from random import *

kw_auth = '4963d6ec90d0c9ec140c1fe9f5b2a325dd734b9f'
cw_auth = 'dd10e1670e0342047b917ac6de571c0b631d1aff'
dart_fss.set_api_key(cw_auth)
# open_dart = OpenDartReader(cw_auth)

# 전종목 stock code 가져오기
corpList = dart_fss.get_corp_list()
stockCode = {}
corpCode = {}
for corp in corpList:
    try:
        # (Y: 코스피, K: 코스닥, N:코넥스, E:기타)
        if(corp.corp_cls in ['Y', 'K']):
            stockCode[corp.corp_name] = corp.stock_code
            corpCode[corp.corp_name] = corp.corp_code
    except:
        continue

date_to_process = '2023-03-02'

# 전종목 start_date 전일 종가 시총 가져오기
day_before_start_date = datetime.datetime.strptime(date_to_process, "%Y-%m-%d")
while True:
    day_before_start_date = day_before_start_date - datetime.timedelta(1)
    market_cap = stock.get_market_cap(day_before_start_date)
    if(market_cap.iloc[0]['시가총액']!=0):
        break

page_cnt = 100 # 페이지 당 문서 갯수
page = 1
# lastReportLink = '/dsaf001/main.do?rcpNo=20230302801244'
lastReportLink = '' # 마지막으로 처리한 report link 저장 -> 새로 report 찾을때 사용
foundReportLinks = list()
while True:
    start_time = time.time()

    print('trying to find new reports...')
    earning_reports = []
    while True:
        # api 이용없이 공시 가져오기
        reports = get_disclosure(date_to_process, page, page_cnt, foundReportLinks, lastReportLink).rows

        # 공시 목록 중 처리 가능한 것들만 남기고 필터링
        for report in reports:
            foundReportLinks.append(report.report_link)

            # 코스피, 코스닥 아닌 경우 필터링
            if report.corp_cls != ('유') and report.corp_cls != ('코'):
                print(report.corp_name, report.tag, "-pass: no kospi/kosdaq")
                continue

            # 정정, 월별, 자회사, 연장 필터링
            is_correction = report.report_nm.find("정정") != -1
            is_monthly = report.report_nm.find("월별") != -1
            is_subsidiary = report.report_nm.find("자회사") != -1
            is_extension = report.report_nm.find("연장") != -1
            if is_correction or is_monthly or is_subsidiary or is_extension:
                print(report.corp_name, report.report_nm, "-pass: 정정/월별/자회사 report")
                continue

            # 스팩 필터링
            is_spac = report.corp_name.find("스팩") != -1
            if is_spac:
                print(report.corp_name, "-pass: 스팩")
                continue

            earning_reports.append(report) # 최신순으로 저장

        if(len(reports) == page_cnt):
            page = page + 1
            time.sleep(0.01)
        else:
            page = 1
            break
    print('number of reports found: ', len(earning_reports))

    # 개별 공시 파싱 처리
    earning_reports.reverse() # 오래된 순으로 순서 뒤집기
    for report in tqdm(earning_reports):
        is_periodic_report = (report.report_nm.find("사업보고서") != -1) or \
                             (report.report_nm.find("반기보고서") != -1) or \
                             (report.report_nm.find("분기보고서") != -1)

        print('개별 공시 파싱 처리: appended ', report.corp_name)
        if report.report_nm.find("잠정") != -1:
            # template.1 - 영업(잠정)실적(공정공시)
            earning_data = parser_provisional_earning(report, market_cap.loc[stockCode[report.corp_name]]['시가총액'], stockCode[report.corp_name])
        elif report.report_nm.find("30%") != -1:
            # template.2 - 매출액또는손익구조30%(대규모법인은15%)이상변경
            earning_data = parser_30pcnt_change(report, market_cap.loc[stockCode[report.corp_name]]['시가총액'], stockCode[report.corp_name])
        elif report.report_nm.find("보고서") != -1:
            # template.3 - 사업/반기/분기 보고서
            earning_data = parser_quaterly_report(report, market_cap.loc[stockCode[report.corp_name]]['시가총액'], stockCode[report.corp_name], corpCode[report.corp_name])
        time.sleep(0.06)

    end_time = time.time()
    elapsed_time = end_time - start_time
    if(elapsed_time < 1.0):
        time.sleep(1.0-elapsed_time+0.1*random())
