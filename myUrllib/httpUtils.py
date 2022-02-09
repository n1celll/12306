# -*- coding: utf8 -*-
import json
import random
import socket
from collections import OrderedDict
from time import sleep
import requests
import TickerConfig
from agency.agency_tools import proxy
from config import logger


class HTTPClient(object):

    def __init__(self, is_proxy, cdn_list=None):
        """
        cdnList试试切换不包括查询的cdn，防止查询cdn污染登陆和下单cdn
        :param is_proxy: 是否使用代理
        """
        self._s = requests.Session()
        self._s.headers.update(self._set_header_default())
        self._cdn = None
        self.cdnList = cdn_list
        self._proxies = None
        if is_proxy == 1:
            self.proxy = proxy()
            self._proxies = self.proxy.setProxy()
            # print(u"设置当前代理ip为 {}, 请注意代理ip是否可用！！！！！请注意代理ip是否可用！！！！！请注意代理ip是否可用！！！！！".format(self._proxies))

    @staticmethod
    def get_user_agent():
        return f'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) ' \
               f'Chrome/97.0.{str(random.randint(5000, 7000))}.99 Safari/537.36'

    def _set_header_default(self):
        header_dict = OrderedDict()
        header_dict["Accept-Encoding"] = "gzip, deflate"
        header_dict[
            "User-Agent"] = self.get_user_agent()
        header_dict["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        header_dict["Origin"] = "https://kyfw.12306.cn"
        header_dict["Connection"] = "keep-alive"
        return header_dict

    def set_cookies(self, kwargs):
        """
        设置cookies
        :param kwargs:
        :return:
        """
        for kwarg in kwargs:
            for k, v in kwarg.items():
                self._s.cookies.set(k, v)

    def get_cookies(self):
        """
        获取cookies
        :return:
        """
        return self._s.cookies.values()

    def del_cookies(self):
        """
        删除所有的key
        :return:
        """
        self._s.cookies.clear()

    def del_cookies_by_key(self, key):
        """
        删除指定key的session
        :return:
        """
        self._s.cookies.set(key, None)

    def set_headers(self, headers):
        self._s.headers.update(headers)
        return self

    def reset_headers(self):
        self._s.headers.clear()
        self._s.headers.update(self._set_header_default())

    def get_headers_host(self):
        return self._s.headers["Host"]

    def set_headers_host(self, host):
        self._s.headers.update({"Host": host})
        return self

    def set_headers_user_agent(self):
        self._s.headers.update({"User-Agent": self.get_user_agent()})

    def get_headers_user_agent(self):
        return self._s.headers["User-Agent"]

    def get_headers_referer(self):
        return self._s.headers["Referer"]

    def set_headers_referer(self, referer):
        self._s.headers.update({"Referer": referer})
        return self

    @property
    def cdn(self):
        return self._cdn

    @cdn.setter
    def cdn(self, cdn):
        self._cdn = cdn

    def send(self, urls, data=None, **kwargs):
        """send request to url.If response 200,return response, else return None."""
        allow_redirects = False
        is_logger = urls.get("is_logger", False)
        req_url = urls.get("req_url", "")
        re_try = urls.get("re_try", 0)
        s_time = urls.get("s_time", 0)
        is_cdn = urls.get("is_cdn", False)
        is_test_cdn = urls.get("is_test_cdn", False)
        error_data = {"code": 99999, "message": "重试次数达到上限"}
        if data:
            method = "post"
            self.set_headers({"Content-Length": "{0}".format(len(data))})
        else:
            method = "get"
            self.reset_headers()
        if TickerConfig.RANDOM_AGENT == 1:
            self.set_headers_user_agent()
        self.set_headers_referer(urls["Referer"])
        if is_logger:
            logger.log(
                u"url: {0}\n入参: {1}\n请求方式: {2}\n".format(req_url, data, method))
        self.set_headers_host(urls["Host"])
        if is_test_cdn:
            url_host = self._cdn
        elif is_cdn:
            if self._cdn:
                # print(u"当前请求cdn为{}".format(self._cdn))
                url_host = self._cdn
            else:
                url_host = urls["Host"]
        else:
            url_host = urls["Host"]
        http = urls.get("httpType") or "https"
        for i in range(re_try):
            try:
                # sleep(urls["s_time"]) if "s_time" in urls else sleep(0.001)
                sleep(s_time)
                try:
                    requests.packages.urllib3.disable_warnings()
                except Exception:
                    pass
                response = self._s.request(method=method,
                                           timeout=5,
                                           proxies=self._proxies,
                                           url=http + "://" + url_host + req_url,
                                           data=data,
                                           allow_redirects=allow_redirects,
                                           verify=False,
                                           **kwargs)
                if response.status_code == 200 or response.status_code == 302:
                    if urls.get("not_decode", False):
                        return response.content
                    if response.content:
                        if is_logger:
                            logger.log(
                                f"出参：{response.content.decode()}")
                        if urls["is_json"]:
                            try:
                                return json.loads(
                                    response.content.decode()
                                    if isinstance(response.content, bytes) else response.content)
                            except Exception as e:
                                print(e)
                                continue
                        else:
                            return response.content.decode("utf8", "ignore") if isinstance(response.content,
                                                                                           bytes) else response.content
                    else:
                        print(f"url: {urls['req_url']}返回参数为空, 接口状态码: {response.status_code}")

                        logger.log(
                            "url: {} 返回参数为空".format(urls["req_url"]))
                        if self.cdnList:
                            # 如果下单或者登陆出现cdn 302的情况，立马切换cdn
                            url_host = self.cdnList.pop(random.randint(0, 4))
                        continue
                else:
                    sleep(urls["re_time"])
            except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                pass
            except socket.error:
                pass
        return error_data
