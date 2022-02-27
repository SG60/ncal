# config

```python
>>> from ncal.config import load_settings
>>> configuration = load_settings(
...     notion_api_token="secret_123456",
...     database_id="1234567",
...     url_root="https://www.notion.so/exampleuser/afeeec3434177a5aefde223455?v=1462bb2343466546ae54e&p=",
... )
>>> type(configuration)
<class 'ncal.config.Settings'>
>>> configuration.default_calendar_name
'Notion Events'

```

::: ncal.config