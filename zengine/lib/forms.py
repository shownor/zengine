from datetime import datetime, date
from pyoko.field import DATE_FORMAT

from pyoko.form import Form

class JsonForm(Form):
    def serialize(self):
        result = {
            "schema": {
                "title": self.title,
                "type": "object",
                "properties": {},
                "required": []
            },
            "form": [],
            "model": {}
        }
        for itm in self._serialize():
            if isinstance(itm['value'], (date, datetime)):
                itm['value'] = itm['value'].strftime(DATE_FORMAT)
            result["schema"]["properties"][itm['name']] = { 'type': itm['type'],
                                                            'title': itm['title']}
            result["model"][itm['name']] = itm['value'] or itm['default']
            result["form"].append(itm['name'])
            if itm['required']:
                result["schema"]["required"].append(itm['name'])
        return result


