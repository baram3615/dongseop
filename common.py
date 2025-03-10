import datetime 
import time

#df의 timestamp 행을 Windowing 하기위해 int 형태로 바꾸는 함수
def convert_to_timestamp(row):
    return time.mktime(datetime.datetime.strptime(row, '%Y-%m-%d %H:%M:%S').timetuple())

#+00:00 를 없애고 KST 로 바꾸는 함수
def convert_gmt_to_kst(row):
    return str(datetime.datetime.strptime(row, '%Y-%m-%d %H:%M:%S+00:00')+datetime.timedelta(hours=9)-datetime.timedelta(minutes=1))

#timestamp int 형태를 string 형태의 yyy-MM-dd HH:mm:ss 로 바꾸기
def convert_timestamp_to_datetime_str(row):
    return str(datetime.datetime.fromtimestamp(row))
#time.mktime(datetime.datetime.strptime(df['timestamp'][0], '%Y-%m-%d %H:%M:%S+00:00').timetuple())