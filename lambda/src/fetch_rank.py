from google.oauth2 import service_account
from googleapiclient.discovery import build
import boto3
import json
import logging
import os
import re
import traceback
import requests

SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
CLIENT_SECRET_SSM_KEY = os.environ.get('CLIENT_SECRET_SSM_KEY')
VIEW_ID = os.environ.get('VIEW_ID')
OUT_S3_BUCKET = os.environ.get('OUT_S3_BUCKET')
OUT_JSON_KEY = os.environ.get('OUT_JSON_KEY')
SITE_BASE_URL = os.environ.get('SITE_BASE_URL')

s3 = boto3.resource('s3')
ssm = boto3.client('ssm')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_ssm_param(key):
    # type: (str) -> str
    """ Get parameter fron SSM Parameter Store.
    Args:
        key: string for SSM parameter store key
    Returns:
        string
    """
    response = ssm.get_parameters(
        Names=[
            key,
        ],
        WithDecryption=True
    )
    return response['Parameters'][0]['Value']


def initialize_analyticsreporting():
    # type: () -> build
    """Initializes an Analytics Reporting API V4 service object.
    Returns:
      An authorized Analytics Reporting API V4 service object.
    """
    logger.info('initialize analytics reporting')
    client_secret_string = get_ssm_param(CLIENT_SECRET_SSM_KEY)

    client_secret = json.loads(client_secret_string)
    credentials = service_account.Credentials.from_service_account_info(
        client_secret, scopes=SCOPES)

    # Build the service object.
    analytics = build('analyticsreporting', 'v4',
                      credentials=credentials,
                      cache_discovery=False)
    return analytics


def get_report(analytics):
    # type: (build) -> dict
    """Queries the Analytics Reporting API V4.
    Args:
      analytics: An authorized Analytics Reporting API V4 service object.
    Returns:
      The Analytics Reporting API V4 response.
    """
    logger.info('get report')
    return analytics.reports().batchGet(
        body={
            'reportRequests': [
                {
                    'viewId': VIEW_ID,
                    'dateRanges': [{'startDate': '7daysAgo', 'endDate': 'yesterday'}],
                    'metrics': [{'expression': 'ga:pageviews'}],
                    'dimensions': [{'name': 'ga:pagePath'}]
                }]
        }
    ).execute()


def calc(response):
    # type: (dict) -> list
    """Calculate page views of each page path.
    Args:
        response: The Analytics Reporting API V4 response.
    """
    logger.info('calculate page views')
    calc_res = dict()
    pv_summary = []
    report = response.get('reports', [])[0]
    for report_data in report.get('data', {}).get('rows', []):
        # get page path
        page_path = report_data.get('dimensions', [])[0]
        # ignore query parameters
        page_path = re.sub(r'\?.+$', '', page_path)

        # get page view
        page_view = int(report_data.get('metrics', [])[0].get('values')[0])

        if page_path in calc_res:
            calc_res[page_path] += page_view
        else:
            calc_res[page_path] = page_view

    for path in calc_res:
        # skip top page
        if path == '' or path == '/':
            continue

        pv_summary.append({
            'page_path': path,
            'page_views': calc_res[path]
        })

    # sort by page views
    pv_summary.sort(
        key=lambda path_data: path_data['page_views'], reverse=True)

    return pv_summary


def report_to_rank(report, count=5):
    # type: (list, int) -> list
    """ Convert report data to ranking data
    Args:
        report: list object to convert
        count: number of ranking post. default is 5
    Returns:
        list
    """
    logger.info('convert report data to ranking data')
    if count == 0 or len(report) < count:
        count = 5

    rank_tmp = report[:count]

    rank = list()
    try:
        for rt in rank_tmp:
            post_url = SITE_BASE_URL + rt['page_path']
            post_title, post_date = get_post_title_and_date(post_url)
            rank.append({
                'post_url': post_url,
                'post_title': post_title,
                'post_date': post_date})
    except Exception:
        print('An error occured in getting post title process.')
        print(traceback.format_exc())

    return rank


def get_post_title_and_date(post_url):
    # type: (str) -> str
    """ Get post title from post url
    Args:
        post_url: URL of the post
    Returns:
        string, string
    """

    logger.info('get post title from post url: ' + post_url)
    post_title = ''
    post_date = ''

    try:
        res = requests.get(post_url)
        body = res.text
        post_title = re.sub(r'[\s\S]+<title>(.*)<\/title>[\s\S]+', r'\1', body)
        post_date = re.sub(
            r'[\s\S]+<span class="sub">(\d{4}-\d{2}-\d{2})<\/span>[\s\S]+', r'\1', body)
        if re.search(r'^\d{4}-\d{2}-\d{2}$', post_date) is None:
            post_date = ''
    except Exception:
        print(f'Failed to get post title of "{post_url}"')
        print(traceback.format_exc())

    return post_title, post_date


def put_to_s3(data, key):
    # type: (dict, str) -> None
    """ Put object to S3 bucket
    Args:
        data: dict or list object to put as JSON.
        key: object key
    """

    logger.info('put object to S3')
    try:
        s3obj = s3.Object(OUT_S3_BUCKET, key)
        body = json.dumps(data, ensure_ascii=False)
        s3obj.put(
            Body=body,
            ContentType='application/json;charset=UTF-8',
            CacheControl='public, max-age=1209600')
    except Exception:
        logger.error('Put count data failed: %s', traceback.format_exc())


def main(event, context):
    analytics = initialize_analyticsreporting()
    response = get_report(analytics)
    summary = calc(response)
    rank = report_to_rank(summary)
    put_to_s3(rank, OUT_JSON_KEY)


if __name__ == '__main__':
    print('Running at local...\n\n')

    analytics = initialize_analyticsreporting()
    response = get_report(analytics)
    summary = calc(response)
    rank = report_to_rank(summary)
    print(json.dumps(rank, indent=2, ensure_ascii=False))
