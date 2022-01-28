# -*- coding=utf-8 -*-
import datetime
import random
import os
import socket
import sys
import threading
import time
import TickerConfig
import wrapcache
from agency.cdn_utils import CDNProxy, open_cdn_file
from config import urlConf, configCommon
from config.TicketEnmu import ticket
from config.configCommon import seat_conf_2, seat_conf
from config.getCookie import getDrvicesID
from init.login import GoLogin
from inter.AutoSubmitOrderRequest import autoSubmitOrderRequest
from inter.ChechFace import chechFace
from inter.CheckUser import checkUser
from inter.GetPassengerDTOs import getPassengerDTOs
from inter.LiftTicketInit import liftTicketInit
from inter.Query import query
from inter.SubmitOrderRequest import submitOrderRequest
from myException.PassengerUserException import PassengerUserException
from myException.UserPasswordException import UserPasswordException
from myException.ticketConfigException import ticketConfigException
from myException.ticketIsExitsException import ticketIsExitsException
from myException.ticketNumOutException import ticketNumOutException
from myUrllib.httpUtils import HTTPClient


class select:
    """
    快速提交车票通道
    """
    def __init__(self):
        self.cdn_list = open_cdn_file("filter_cdn_list")
        self.get_ticket_info()
        self._station_seat = [seat_conf[x] for x in TickerConfig.SET_TYPE]
        self.auto_code_type = TickerConfig.AUTO_CODE_TYPE
        self.httpClint = HTTPClient(TickerConfig.IS_PROXY, self.cdn_list)
        self.httpClint.cdn = self.cdn_list[random.randint(0, 4)]
        self.urls = urlConf.urls
        self.login = GoLogin(self, TickerConfig.IS_AUTO_CODE, self.auto_code_type)
        self.cookies = ""
        self.queryUrl = "leftTicket/queryO"
        self.passengerTicketStrList = ""
        self.passengerTicketStrByAfterLate = ""
        self.oldPassengerStr = ""
        self.set_type = ""
        self.flag = True

    @staticmethod
    def get_ticket_info():
        """
        获取配置信息
        :return:
        """

        print(u"*" * 100)
        print(f"检查当前版本为: {TickerConfig.RE_VERSION}")
        version = sys.version.split(" ")[0]
        _v = version.split(".")
        if _v[0] != "3" or int(_v[1]) < 6:
            raise Exception(f"检查当前python版本为：{version}，目前版本只支持3.6以上")

        print(
            f"当前配置：\n出发站：{TickerConfig.FROM_STATION}\n到达站：{TickerConfig.TO_STATION}\n车次: {','.join(TickerConfig.STATION_TRAINS) or '所有车次'}\n乘车日期：{','.join(TickerConfig.STATION_DATES)}\n坐席：{','.join(TickerConfig.SET_TYPE)}\n是否有票优先提交：{TickerConfig.IS_MORE_TICKET}\n乘车人：{TickerConfig.TICKET_PEOPLES}\n"
            f"刷新间隔: 随机(1-3S)\n僵尸票关小黑屋时长: {TickerConfig.TICKET_BLACK_LIST_TIME}\n下单接口: {TickerConfig.ORDER_TYPE}\n下单模式: {TickerConfig.ORDER_MODEL}\n预售踩点时间:{TickerConfig.OPEN_TIME}")
        print(u"*" * 100)

    def station_table(self, from_station, to_station):
        """
        读取车站信息
        :param station:
        :return:
        """
        path = os.path.join(os.path.dirname(__file__), '../station_name.txt')
        try:
            with open(path, encoding="utf-8") as result:
                info = result.read().split('=')[1].strip("'").split('@')
        except Exception:
            with open(path) as result:
                info = result.read().split('=')[1].strip("'").split('@')
        del info[0]
        station_name = {}
        for i in range(0, len(info)):
            n_info = info[i].split('|')
            station_name[n_info[1]] = n_info[2]
        try:
            from_station = station_name[from_station.encode("utf8")]
            to_station = station_name[to_station.encode("utf8")]
        except KeyError:
            from_station = station_name[from_station]
            to_station = station_name[to_station]
        return from_station, to_station

    def call_login(self, auth=False):
        """
        登录回调方法
        :return:
        """
        if auth:
            return self.login.auth()
        else:
            configCommon.checkSleepTime(self)  # 防止网上启动晚上到点休眠
            self.login.go_login()

    def check_start_time(self):
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        print(f'当前时间为: {now_str}')
        try:
            open_time = datetime.datetime.strptime(TickerConfig.OPEN_TIME, "%Y-%m-%d %H:%M:%S")
            print(f'预售时间为：{TickerConfig.OPEN_TIME}, ')
        except Exception:
            open_time = now
            print("预售时间格式错误, 系统将立即开始抢票")
        advance_time = TickerConfig.ADVANCE_TIME
        if now + datetime.timedelta(seconds=advance_time) < open_time:
            start_try_time = (open_time + datetime.timedelta(seconds=-advance_time))
            print(f'将在 {start_try_time.strftime("%Y-%m-%d %H:%M:%S")} 开始抢票')
            while now < start_try_time:
                now = datetime.datetime.now()
                time.sleep(0.0001)
        print(f"抢票开始，预售开启时间为: {open_time}")

    def main(self):
        l = liftTicketInit(self)
        l.reqLiftTicketInit()
        getDrvicesID(self)
        advance_time = TickerConfig.ADVANCE_TIME
        if isinstance(advance_time, int) and advance_time > 0:
            self.check_start_time()
        self.call_login()
        check_user = checkUser(self)
        t = threading.Thread(target=check_user.sendCheckUser)
        t.setDaemon(True)
        t.start()
        from_station, to_station = self.station_table(TickerConfig.FROM_STATION, TickerConfig.TO_STATION)
        num = 0
        s = getPassengerDTOs(selectObj=self, ticket_peoples=TickerConfig.TICKET_PEOPLES)
        passenger = s.sendGetPassengerDTOs()
        wrapcache.set("user_info", passenger, timeout=9999999)
        if TickerConfig.ORDER_MODEL == 1:
            sleep_time_s = 0.3
            sleep_time_t = 0.5
        else:
            sleep_time_s = TickerConfig.MIN_TIME
            sleep_time_t = TickerConfig.MAX_TIME

        while 1:
            try:
                num += 1
                now = datetime.datetime.now()  # 感谢群里大佬提供整点代码
                configCommon.checkSleepTime(self)  # 晚上到点休眠
                q = query(selectObj=self,
                          from_station=from_station,
                          to_station=to_station,
                          from_station_h=TickerConfig.FROM_STATION,
                          to_station_h=TickerConfig.TO_STATION,
                          _station_seat=self._station_seat,
                          station_trains=TickerConfig.STATION_TRAINS,
                          station_dates=TickerConfig.STATION_DATES,
                          ticke_peoples_num=len(TickerConfig.TICKET_PEOPLES),
                          )
                queryResult = q.sendQuery()
                # 查询接口
                if queryResult.get("status"):
                    train_no = queryResult.get("train_no", "")
                    train_date = queryResult.get("train_date", "")
                    stationTrainCode = queryResult.get("stationTrainCode", "")
                    secretStr = queryResult.get("secretStr", "")
                    secretList = queryResult.get("secretList", "")
                    seat = queryResult.get("seat", "")
                    leftTicket = queryResult.get("leftTicket", "")
                    query_from_station_name = queryResult.get("query_from_station_name", "")
                    query_to_station_name = queryResult.get("query_to_station_name", "")
                    is_more_ticket_num = queryResult.get("is_more_ticket_num", len(TickerConfig.TICKET_PEOPLES))
                    if wrapcache.get(train_no):
                        print(ticket.QUEUE_WARNING_MSG.format(train_no))
                    else:
                        # 获取联系人
                        s = getPassengerDTOs(selectObj=self, ticket_peoples=TickerConfig.TICKET_PEOPLES,
                                             set_type="" if isinstance(seat, list) else seat_conf_2[seat],
                                             # 候补订单需要设置多个坐席
                                             is_more_ticket_num=is_more_ticket_num)
                        getPassengerDTOsResult = s.getPassengerTicketStrListAndOldPassengerStr(secretStr, secretList)
                        if getPassengerDTOsResult.get("status", False):
                            self.passengerTicketStrList = getPassengerDTOsResult.get("passengerTicketStrList", "")
                            self.passengerTicketStrByAfterLate = getPassengerDTOsResult.get(
                                "passengerTicketStrByAfterLate", "")
                            self.oldPassengerStr = getPassengerDTOsResult.get("oldPassengerStr", "")
                            self.set_type = getPassengerDTOsResult.get("set_type", "")
                        # 提交订单
                        # 订单分为两种，一种为抢单，一种为候补订单
                        if secretStr:  # 正常下单
                            if TickerConfig.ORDER_TYPE == 1:  # 快速下单
                                a = autoSubmitOrderRequest(selectObj=self,
                                                           secretStr=secretStr,
                                                           train_date=train_date,
                                                           passengerTicketStr=self.passengerTicketStrList,
                                                           oldPassengerStr=self.oldPassengerStr,
                                                           train_no=train_no,
                                                           stationTrainCode=stationTrainCode,
                                                           leftTicket=leftTicket,
                                                           set_type=self.set_type,
                                                           query_from_station_name=query_from_station_name,
                                                           query_to_station_name=query_to_station_name,
                                                           )
                                a.sendAutoSubmitOrderRequest()
                            elif TickerConfig.ORDER_TYPE == 2:  # 普通下单
                                sor = submitOrderRequest(self, secretStr, from_station, to_station, train_no,
                                                         self.set_type,
                                                         self.passengerTicketStrList, self.oldPassengerStr, train_date,
                                                         TickerConfig.TICKET_PEOPLES)
                                sor.sendSubmitOrderRequest()
                        elif secretList:  # 候补订单
                            c = chechFace(self, secretList, train_no)
                            c.sendChechFace()
                else:
                    random_time = round(random.uniform(sleep_time_s, sleep_time_t), 2)
                    nateMsg = ' 无候补机会' if TickerConfig.ORDER_TYPE == 2 else ""
                    print(f"正在第{num}次查询 停留时间：{random_time} 乘车日期: {','.join(TickerConfig.STATION_DATES)} 车次：{','.join(TickerConfig.STATION_TRAINS) or '所有车次'} 下单无票{nateMsg} 耗时：{(datetime.datetime.now() - now).microseconds / 1000} {queryResult.get('cdn')}")
                    time.sleep(random_time)
            except PassengerUserException as e:
                print(e)
                break
            except ticketConfigException as e:
                print(e)
                break
            except ticketIsExitsException as e:
                print(e)
                break
            except ticketNumOutException as e:
                print(e)
                break
            except UserPasswordException as e:
                print(e)
                break
            except ValueError as e:
                if e == "No JSON object could be decoded":
                    print("12306接口无响应，正在重试")
                else:
                    print(e)
            except KeyError as e:
                print(e)
            except TypeError as e:
                print("12306接口无响应，正在重试 {0}".format(e))
            except socket.error as e:
                print(e)


if __name__ == '__main__':
    s = select()
    cdn = s.station_table("长沙", "深圳")
