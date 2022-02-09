# coding=utf-8
import re


class liftTicketInit:
    def __init__(self, session):
        self.session = session

    def reqLiftTicketInit(self):
        """
        请求抢票页面
        :return:
        """
        urls = self.session.urls["left_ticket_init"]
        # 获取初始化的结果
        result = self.session.httpClint.send(urls)
        try:
            # 用正则表达式查出CLeftTicketUrl的值
            match_obj = re.search('var CLeftTicketUrl = \'(.*)\'', result, re.M | re.I)
            if match_obj:
                # 如果有值，替换queryUrl
                self.session.queryUrl = match_obj.group(1)
                return True
        except Exception:
            return


