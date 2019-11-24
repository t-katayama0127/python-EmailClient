import poplib
import email
from email.header import decode_header, make_header
import logging
from typing import Iterable, Callable
import functools

__all__ = ["parse_email", "POP3Client", "MAIL_HEADER_NAMES"]

MAIL_HEADER_NAMES = ["From", "To", "Subject", "Date", "Message-Id", "In-Reply-To",
                     "References", "Reply-To", "Received", "Mime-Version",
                     "Content-Type", "Content-Transfer-Encoding", "Content-Disposition"]


def parse_email(msg: bytes) -> dict:
    """
    email をパースした結果を戻す
    ---
    Parameters:
        msg: email
    ---
    Returns:
        {ヘッダ名: 内容, ... ,"Body": [{本文パートヘッダ名: 内容, ... , "data": 本文}, ...]}
    """
    msg_data = {}
    msg = email.message_from_bytes(msg)
    for header_name in MAIL_HEADER_NAMES:
        header = msg[header_name]
        if header:
            msg_data[header_name] = str(make_header(decode_header(header)))

    body_parts = []

    for part in msg.walk():
        payload = part.get_payload(decode=True)
        if payload:
            body_data = {}
            for header_name in MAIL_HEADER_NAMES:
                header = part.get(header_name)
                if header:
                    body_data[header_name] = part.get(header_name)
            charset = part.get_content_charset()
            if charset:
                payload = payload.decode(charset, "ignore")
            body_data["data"] = payload
            body_parts.append(body_data)

    msg_data["Body"] = body_parts

    return msg_data


class POP3Client:
    """
    POP3サーバに問い合わせるためのクラス
    コンテキストマネージャとしても機能する
    ---
    Parameters:
        user: ログインユーザ名
        password: ログインパスワード
        host: pop3サーバのホスト名
        port: pop3サーバのポート
        old_uid: 受信済みメッセージの unique id のリスト
        use_ssl: True のとき POP3_SSL を使う
        auth_method: 認証にAPOPまたはRPOPを使用するとき、"apop" または "rpop" を指定する)
        option: poplib.POP3 または poplib.POP3_SSL コンストラクタに渡す host, port 以外の引数の辞書
        logger: pop3通信を行ったときのサーバからのメッセージをログとして記録するLogger
    """
    def __init__(self, user: str, password: str, host: str,
                 port: int = None, old_uid: Iterable = None, use_ssl: bool = True,
                 auth_method: str = None, option: dict = {}, logger: logging.Logger = None):
        self.host = host
        if use_ssl:
            self.port = port if port else poplib.POP3_SSL_PORT
            self.pop3_cls = POP3_SSL_plus_logging
        else:
            self.port = port if port else poplib.POP3_PORT
            self.pop3_cls = POP3_plus_logging
        self.user = user
        self.password = password
        self.old_uid = set(old_uid) if old_uid else set()
        self.pop3 = None
        self.auth_method = auth_method
        self.option = option
        self.logger = logger if logger else self._get_default_logger()

    def __del__(self):
        try:
            self.quit()
        except Exception:
            pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, ex_type, ex_value, trace):
        self.quit()

    def connect(self):
        """
        POP3オブジェクトを作成し、認証を行う
        """
        self.pop3 = self.pop3_cls(self.host, self.port, logger=self.logger, **self.option)
        try:
            if self.auth_method == "apop":
                self.pop3.apop(self.user, self.password)
            elif self.auth_method == "rpop":
                self.pop3.rpop(self.user)
                self.pop3.pass_(self.password)
            else:
                self.pop3.user(self.user)
                self.pop3.pass_(self.password)
        except Exception:
            self.quit()
            raise

    def quit(self):
        """
        POP3接続を閉じ、変更をコミットし、サーバの受信ボックスのロックを解除する
        """
        self.pop3.quit()
        self.pop3 = None

    def get_all_unique_id(self) -> dict:
        """
        サーバの受信ボックスにあるすべてのメッセージの unique id と message number の辞書を戻す
        ---
        Returns:
            {unique_id: message_number, ...}
        """
        all_uid = map(self._parse_unique_id, self.pop3.uidl()[1])
        return {x[0]: x[1] for x in all_uid}

    def get_new_unique_id(self) -> dict:
        """
        受信済みでないメッセージの unique id と message number の辞書を戻す
        ---
        Returns:
            {unique_id: message_number, ...}
        """
        all_uid = self.get_all_unique_id()
        return {x: all_uid[x] for x in all_uid.keys() - self.old_uid}

    def get_messages(self, uid_dict: dict) -> dict:
        """
        uid_dict で指定されたメッセージを取得する
        ---
        Parameters:
            uid_dict: {unique_id: message_number, ...}
        ---
        Returns:
            {unique_id: {ヘッダ名: 内容, ... ,"Body": [{本文パートヘッダ名: 内容, ... , "data": 本文}, ...]}, ...}
        """
        msg_dict = {}
        for uid, msg_no in uid_dict.items():
            msg_dict[uid] = self._parse_message(self.pop3.retr(msg_no))
        self.old_uid |= msg_dict.keys()
        return msg_dict

    def get_all_messages(self) -> dict:
        """
        サーバにあるすべてのメッセージを取得する
        ---
        Returns:
            {unique_id: {ヘッダ名: 内容, ... ,"Body": [{本文パートヘッダ名: 内容, ... , "data": 本文}, ...]}, ...}
        """
        return self.get_messages(self.get_all_unique_id())

    def get_new_messages(self) -> dict:
        """
        受信済みでないメッセージを取得する
        ---
        Returns:
            {unique_id: {ヘッダ名: 内容, ... ,"Body": [{本文パートヘッダ名: 内容, ... , "data": 本文}, ...]}, ...}
        """
        return self.get_messages(self.get_new_unique_id())

    def delete_messages(self, uid_list: Iterable):
        """
        uid_list に指定されたメッセージに削除フラグを立てる
        ---
        Parameters:
            uid_list: 削除するメッセージのユニークIDを格納したIterable
        """

    def undo_delete(self):
        """
        削除フラグをすべて取り消す
        """
        self.pop3.rset()

    def _parse_unique_id(self, uid_bytes: bytes) -> (str, int):
        """
        POP3.uidl の2番目の戻り値の要素をパースした結果を戻す
        ---
        Parameters:
            uid_bytes: POP3.uidl の2番目の戻り値の要素
        ---
        Returns:
            unique_id, message_number
        """
        msg_no, uid = uid_bytes.decode().split(' ')
        msg_no = int(msg_no)
        return uid, msg_no

    def _parse_message(self, retr_result: tuple) -> dict:
        """
        POP3.retr の戻り値をパースした結果を戻す
        ---
        Parameters:
            retr_result: POP3.retr の戻り値
        ---
        Returns:
            {ヘッダ名: 内容, ... ,"Body": [{本文パートヘッダ名: 内容, ... , "data": 本文}, ...]}
        """
        msg = b'\r\n'.join(retr_result[1])
        return parse_email(msg)

    def _get_default_logger(self):
        logger = logging.getLogger(f'POP3/{self.host}/{self.user}')
        logger.setLevel('INFO')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(fmt="%(levelname)s\t%(asctime)s\t%(name)s\t%(message)s",
                                          datefmt="%Y-%m-%d %H:%M:%S")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger


def add_POP3_res_logging(func) -> Callable:
    """
    POP3, POP3_SSLクラスのサーバ問い合わせメソッドに、
    サーバからのレスポンスをself.loggerに渡す処理を追加するデコレータ
    """
    if not callable(func):
        return func

    if func.__name__ in ('getwelcome', 'user', 'pass_', 'dele',
                         'noop', 'rset', 'quit', 'rpop', 'apop', 'utf8', 'stls'):
        def get_message(result):
            return result.decode()
    elif func.__name__ in ('retr', 'top'):
        def get_message(result):
            return result[0].decode()
    elif func.__name__ in ('capa',):
        def get_message(result):
            return str(result)
    elif func.__name__ in ('list', 'uidl'):
        def get_message(result):
            return result[0].decode() if isinstance(result, tuple) else result.decode()
    elif func.__name__ in ('stat',):
        def get_message(result):
            return f'massage_count={result[0]}, mailbox_size={result[1]}'
    else:
        return func

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)
            msg = get_message(result)
            if msg:
                self.logger.info(f"{wrapper.__name__} -> {msg}")
            return result
        except poplib.error_proto as e:
            self.logger.error(e.args[0].decode())
            raise
        except Exception:
            self.logger.exception('UnexpectedError')
            raise

    return wrapper


class POP3_plus_logging_meta(type):
    def __new__(cls, classname, bases, attributes):
        instance = super().__new__(cls, classname, bases, attributes)
        for attr in dir(instance):
            value = getattr(instance, attr)
            if callable(value):
                setattr(instance, attr, add_POP3_res_logging(value))
        return instance


class POP3_plus_logging(poplib.POP3, metaclass=POP3_plus_logging_meta):
    def __init__(self, *args, logger, **kwargs):
        self.logger = logger
        super().__init__(*args, **kwargs)


class POP3_SSL_plus_logging(poplib.POP3_SSL, metaclass=POP3_plus_logging_meta):
    def __init__(self, *args, logger, **kwargs):
        self.logger = logger
        super().__init__(*args, **kwargs)
