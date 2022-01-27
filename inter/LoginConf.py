# coding=utf-8
from config.urlConf import urls


def loginConf(session):
    """
    判断登录是否需要验证码
    :param session:
    :return:
    """
    loginConfUrl = urls.get("loginConf")
    loginConfRsp = session.httpClint.send(urls=loginConfUrl, data={})
    print(loginConfRsp)
    if loginConfRsp and loginConfRsp.get("data", {}).get("is_login_passCode") == "N":
        print("不需要验证码")
        return False
    else:
        print("需要验证码")
        return True


if __name__ == '__main__':
    pass