"""
Test and flesh a /spaces handler-space.

GET /spaces: list all spaces
GET /spaces/{space_name}: 204 if exist
GET /spaces/{space_name}/members: list all members
PUT /spaces/{space_name}: create a space
PUT /spaces/{space_name}/members/{member_name}: add a member
DELETE /spaces/{space_name}/members/{member_name}: remove a member
POST /spaces/{space_name}: Handle subscription, the data package is
  JSON as {"subscriptions": ["space1", "space2", "space3"]}
"""


from test.fixtures import make_test_env, make_fake_space, get_auth

from wsgi_intercept import httplib2_intercept
import wsgi_intercept
import httplib2
import Cookie
import simplejson

from tiddlyweb.store import Store
from tiddlyweb.model.bag import Bag
from tiddlyweb.model.recipe import Recipe
from tiddlyweb.model.user import User

AUTH_COOKIE = None

def setup_module(module):
    make_test_env()
    from tiddlyweb.config import config
    from tiddlyweb.web import serve
    # we have to have a function that returns the callable,
    # Selector just _is_ the callable
    def app_fn():
        return serve.load_app()
    httplib2_intercept.install()
    wsgi_intercept.add_wsgi_intercept('0.0.0.0', 8080, app_fn)
    wsgi_intercept.add_wsgi_intercept('cdent.0.0.0.0', 8080, app_fn)
    module.store = Store(config['server_store'][0],
            config['server_store'][1], {'tiddlyweb.config': config})
    make_fake_space(module.store, 'cdent')
    user = User('cdent')
    user.set_password('cow')
    module.store.put(user)


def teardown_module(module):
    import os
    os.chdir('..')


def test_spaces_list():
    http = httplib2.Http()
    response, content = http.request('http://0.0.0.0:8080/spaces',
            method='GET')
    assert response['status'] == '200'

    info = simplejson.loads(content)
    assert info == ['cdent']

    make_fake_space(store, 'fnd')
    response, content = http.request('http://0.0.0.0:8080/spaces',
            method='GET')
    assert response['status'] == '200'

    info = simplejson.loads(content)
    assert 'cdent' in info
    assert 'fnd' in info


def test_space_exist():
    http = httplib2.Http()
    response, content = http.request('http://0.0.0.0:8080/spaces/cdent',
            method='GET')
    assert response['status'] == '204'
    assert content == ''

    http = httplib2.Http()
    response, content = http.request('http://0.0.0.0:8080/spaces/nancy',
            method='GET')
    assert response['status'] == '404'
    assert 'nancy does not exist' in content


def test_space_members():
    http = httplib2.Http()
    response, content = http.request('http://0.0.0.0:8080/spaces/cdent/members',
            method='GET')
    assert response['status'] == '401'
    cookie = get_auth('cdent', 'cow')

    response, content = http.request('http://0.0.0.0:8080/spaces/cdent/members',
            headers={'Cookie': 'tiddlyweb_user="%s"' % cookie},
            method='GET')
    assert response['status'] == '200'
    info = simplejson.loads(content)
    assert info == ['cdent']

    response, content = http.request('http://0.0.0.0:8080/spaces/nancy/members',
            headers={'Cookie': 'tiddlyweb_user="%s"' % cookie},
            method='GET')
    response['status'] == '404'


def test_create_space():
    cookie = get_auth('cdent', 'cow')
    http = httplib2.Http()
    response, content = http.request('http://0.0.0.0:8080/spaces/cdent',
            headers={'Cookie': 'tiddlyweb_user="%s"' % cookie},
            method='PUT')
    assert response['status'] == '409'

    response, content = http.request('http://0.0.0.0:8080/spaces/extra',
            method='GET')
    assert response['status'] == '404'

    response, content = http.request('http://0.0.0.0:8080/spaces/extra',
            method='PUT')
    assert response['status'] == '403'

    response, content = http.request('http://0.0.0.0:8080/spaces/extra',
            method='PUT',
            headers={'Cookie': 'tiddlyweb_user="%s"' % cookie},
            )
    assert response['status'] == '201'

    response, content = http.request('http://0.0.0.0:8080/spaces/extra/members',
            headers={'Cookie': 'tiddlyweb_user="%s"' % cookie},
            method='GET')
    response['status'] == '200'
    info = simplejson.loads(content)
    assert info == ['cdent']

    bag = store.get(Bag('extra_public'))
    assert bag.policy.owner == 'cdent'
    assert bag.policy.read == []
    assert bag.policy.accept == ['NONE']
    assert bag.policy.manage == ['cdent']
    assert bag.policy.write == ['cdent']
    assert bag.policy.create == ['cdent']
    assert bag.policy.delete == ['cdent']

    bag = store.get(Bag('extra_private'))
    assert bag.policy.owner == 'cdent'
    assert bag.policy.read == ['cdent']
    assert bag.policy.accept == ['NONE']
    assert bag.policy.manage == ['cdent']
    assert bag.policy.write == ['cdent']
    assert bag.policy.create == ['cdent']
    assert bag.policy.delete == ['cdent']

    recipe = store.get(Recipe('extra_public'))
    recipe_list = recipe.get_recipe()
    assert len(recipe_list) == 3
    assert recipe_list[0][0] == 'system'
    assert recipe_list[1][0] == 'tiddlyspace'
    assert recipe_list[2][0] == 'extra_public'

    recipe = store.get(Recipe('extra_private'))
    recipe_list = recipe.get_recipe()
    assert len(recipe_list) == 4
    assert recipe_list[0][0] == 'system'
    assert recipe_list[1][0] == 'tiddlyspace'
    assert recipe_list[2][0] == 'extra_public'
    assert recipe_list[3][0] == 'extra_private'