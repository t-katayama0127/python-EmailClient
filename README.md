# python-EmailClient

## EmailClient.parse_email
Eメールをパースする。  
結果を辞書として戻す

#### Parameters
- msg: bytes  
Eメールの生データ。

#### Returns
- 結果を格納した辞書。
```
{
  "From": "xxx",
  "To": "xxx",
  HeaderName: HeaderValue,
  ...,
  "Body": [
    {
      "Content-Type": "xxx",
      BodyPart1_HeaderName: HeaderValue,
      ...,
      "data": BodyPart1_Body
    },
    {
      BodyPart2
    },
    ...
  ]
}
```

## EmailClient.POP3Client
POP3サーバに問い合わせるためのクラス。  

[contextmanager](https://docs.python.org/ja/3/reference/datamodel.html#with-statement-context-managers) としての機能を持ち、withブロック開始時にPOP3サーバへのコネクションおよび認証を行い、
withブロック終了時にサーバからサインアウトし、メールボックスのロックを開放する。
```
pop3 = EmailClient.POP3Client(user="xxx", password="xxx", host="xxx")

with pop3:
  messages = pop3.get_new_messages()
```

### constructor
#### Parameters
- user: str  
ログインユーザ名
- password: str  
ログインパスワード
- host: str  
POP3サーバのホスト名
- port: int (default None)
POP3サーバのポート番号  
  - 指定がなくSSLを使用しない場合は自動的に poplib.POP3_PORT (=110) が使用される
  - 指定がなくSSLを使用する場合は自動的に poplib.POP3_SSL_PORT (=995) が使用される
- old_uid: Iterable (default None)  
受信済みメッセージの unique id を格納したコレクション  
メッセージが新着かそうでないかを判定するために使用される
- use_ssl: bool (default True)  
True のとき [poplib.POP3_SSL](https://docs.python.org/ja/3/library/poplib.html#poplib.POP3_SSL) クラスを使用する
False のとき [poplib.POP3](https://docs.python.org/ja/3/library/poplib.html#poplib.POP3) クラスを使用する  
- auth_method: str (default None)  
"apop" を指定すると認証の際 [poplib.POP3.apop](https://docs.python.org/ja/3/library/poplib.html#poplib.POP3.apop)
または [poplib.POP3_SSL.apop](https://docs.python.org/ja/3/library/poplib.html#poplib.POP3.apop) メソッドを使用する  
"rpop" を指定すると認証の際 [poplib.POP3.rpop](https://docs.python.org/ja/3/library/poplib.html#poplib.POP3.rpop)
または [poplib.POP3_SSL.rpop](https://docs.python.org/ja/3/library/poplib.html#poplib.POP3.rpop) メソッドを使用する  
- option: dict (default {})  
[poplib.POP3](https://docs.python.org/ja/3/library/poplib.html#poplib.POP3) または 
[poplib.POP3_SSL](https://docs.python.org/ja/3/library/poplib.html#poplib.POP3_SSL) コンストラクタに host, port 以外の引数(timeout, keyfile, etc...)を渡す必要がある場合、辞書として渡す

### EmailClient.POP3Client.connect
POP3サーバへのコネクションおよび認証を行う

### EmailClient.POP3Client.quit
POP3サーバからサインアウトを行い、メールボックスのロックを開放する

### EmailClient.POP3Client.get_all_unique_id
サーバにあるすべてのメッセージの　unique id と message number の辞書を取得する
#### Returns
```
{unique id: message number, ...}
```

### EmailClient.POP3Client.get_new_unique_id
サーバにあるまだ受信していないメッセージの　unique id と message number の辞書を取得する
#### Returns
unique id をキー、message number を値とする辞書
```
{unique id: message number, ...}
```

### EmailClient.POP3Client.get_messages
引数で指定されたメッセージを取得する

#### Parameters
- uid_dict: dict  
unique id をキー、message number を値とする辞書
```
{unique id: message number, ...}
```

#### Returns
unique id をキー、[parse_email](#emailclientparse_email)の戻り値を値とする辞書
```
{
  unique_id: {
    HeaderName: HeaderValue,
    ...,
    "Body": [
      {
        BodyPart1
      },
      ...
    ]
  },
  ...
}
```

### EmailClient.POP3Client.get_all_messages
サーバにあるすべてのメッセージを取得する

#### Returns
[get_messages](#emailclientpop3clientget_messages) と同様の辞書


### EmailClient.POP3Client.get_new_messages
サーバにあるまだ受信していないメッセージを取得する

#### Returns
[get_messages](#emailclientpop3clientget_messages) と同様の辞書
