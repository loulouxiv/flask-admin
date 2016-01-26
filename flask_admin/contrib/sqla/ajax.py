from sqlalchemy import or_

from flask_admin._compat import as_unicode, string_types
from flask_admin.model.ajax import AjaxModelLoader, DEFAULT_PAGE_SIZE
from flask import session as flask_session

from .tools import get_primary_key, has_multiple_pks


class QueryAjaxModelLoader(AjaxModelLoader):
    def __init__(self, name, session, model, **options):
        """
            Constructor.

            :param fields:
                Fields to run query against
        """
        super(QueryAjaxModelLoader, self).__init__(name, options)

        self.session = session
        self.model = model
        self.fields = options.get('fields')
        self.order_by = options.get('order_by')
        self.create_field = options.get('create_field')

        if not self.fields:
            raise ValueError('AJAX loading requires `fields` to be specified for %s.%s' % (model, self.name))

        self._cached_fields = self._process_fields()

        if has_multiple_pks(model):
            raise NotImplementedError('Flask-Admin does not support multi-pk AJAX model loading.')

        self.pk = get_primary_key(model)

    def _process_fields(self):
        remote_fields = []

        for field in self.fields:
            if isinstance(field, string_types):
                attr = getattr(self.model, field, None)

                if not attr:
                    raise ValueError('%s.%s does not exist.' % (self.model, field))

                remote_fields.append(attr)
            else:
                # TODO: Figure out if it is valid SQLAlchemy property?
                remote_fields.append(field)

        return remote_fields

    def format(self, model):
        if not model:
            return None
        if as_unicode(model) != '' and getattr(model, self.pk) is None:
            return ('new', as_unicode(model))
        else:
            return (getattr(model, self.pk), as_unicode(model))

    def get_one(self, pk):
        if pk == 'new':
            print ("Clef : ", pk)
            add_choice = self.model()
            setattr(add_choice, self.create_field, flask_session['search_term' + self.model.__name__]);
            self.session.add(add_choice)
            return add_choice
        else:
            return self.session.query(self.model).get(pk)

    def get_list(self, term, offset=0, limit=DEFAULT_PAGE_SIZE):
        query = self.session.query(self.model)

        filters = (field.ilike(u'%%%s%%' % term) for field in self._cached_fields)
        query = query.filter(or_(*filters))

        if self.order_by:
            query = query.order_by(self.order_by)

        results = query.offset(offset).limit(limit).all()
        if (self.create_field and not term in (getattr(result, self.create_field) for result in results)):
            add_choice = self.model();
            setattr(add_choice, self.create_field, term);
            flask_session['search_term' + self.model.__name__] = term
            setattr(add_choice, self.pk, 'new');
            return [ add_choice ] + results
        else:
            return results


def create_ajax_loader(model, session, name, field_name, options):
    attr = getattr(model, field_name, None)

    if attr is None:
        raise ValueError('Model %s does not have field %s.' % (model, field_name))

    if not hasattr(attr, 'property') or not hasattr(attr.property, 'direction'):
        raise ValueError('%s.%s is not a relation.' % (model, field_name))

    remote_model = attr.prop.mapper.class_
    return QueryAjaxModelLoader(name, session, remote_model, **options)
