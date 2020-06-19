from google.cloud import datastore
import requests
from flask import Blueprint, request, Response, make_response
from bs4 import BeautifulSoup
import re
import json
import datetime
import time
#import pymongo

client = datastore.Client()
#client = pymongo.MongoClient("mongodb://localhost:27017/")
#db = client["amazon"]
bp = Blueprint('tracker', __name__, url_prefix='/tracker')

# convert long URL to short version
def extract_url(url):
    if url.find("www.amazon.com") == -1:
        return None
    index = url.find("/dp/")
    if index != -1:
        index2 = index + 14
        url = "https://www.amazon.com" + url[index:index2]
    else:
        index = url.find("/gp/")
        if index != -1:
            index2 = index + 22
            url = "https://www.amazon.com" + url[index:index2]
        else:
            url = None
    return url

# get price
def get_converted_price(price):
    converted_price = float(re.sub(r"[^\d.]", "", price))
    return converted_price

# fetch details of the product from website
def get_product_details(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36"
    }
    details = {"name": "", "price": 0, "deal": True, "url": ""}
    short_url = extract_url(url)
    if short_url == "":
        details = None
    else:
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.content, "html5lib")
        title = soup.find(id="productTitle")
        price = soup.find(id="priceblock_dealprice")
        if price is None:
            price = soup.find(id="priceblock_ourprice")
            details['deal'] = False
        if title is not None and price is not None:
            details['name'] = title.get_text().strip()
            details['price'] = get_converted_price(price.get_text())
            details['url'] = short_url
        else:
            return None
    return details

# add details to database
def add_product_detail(details):
    new_product = datastore.Entity(key=client.key('Product'))
    ASIN = details["url"][-10:]
    print(ASIN)
    new_product.update({
        'asin': ASIN,
        'details': details,
        'time': str(datetime.datetime.now())
    })
    try:
        client.put(new_product)
        return new_product
    except Exception as identifier:
        print(identifier)
        error_msg = {"Error": "Unsuccessful adding product"}
        return (error_msg, 400)

def add_product(request_content):
    if 'url' not in request_content:
        error_msg = {"Error": "Missing url"}
        return (error_msg, 400)
    details = get_product_details(request_content['url'])
    return add_product_detail(details)

# monitor and update the prices
def track():
    query = client.query(kind='Product')
    products = list(query.fetch())
    while True:
        for p in products:
            url = p['details']['url']
            #print(url)
            if url is None:
                print("not updated")
            else:
                updated_details = get_product_details(url)
                p.update({
                    'details': updated_details,
                    'time': datetime.datetime.now()
                })
                try:
                    client.put(p)
                    print("updated")
                except Exception as identifier:
                    print(identifier)
                    print("not updated")
        time.sleep(600)

def get_products(request):
    query = client.query(kind = 'Product')
    q_limit = int(request.args.get('limit', '10'))
    q_offset = int(request.args.get('offset', '0'))
    g_iterator = query.fetch(limit=q_limit, offset=q_offset)
    pages = g_iterator.pages
    results = list(next(pages))
    if g_iterator.next_page_token:
        next_offset = q_offset + q_limit
        next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
    else:
        next_url = None
    for e in results:
        e["id"] = str(e.key.id)
        e["self"] = request.base_url + '/' + str(e.key.id)
    output = {"products": results}
    if next_url:
        output["next"] = next_url
    return output

# create a new product via POST or view all products via GET
@ bp.route('', methods=['POST', 'GET', 'PUT', 'DELETE'])
def manage_products():
    if 'application/json' not in request.accept_mimetypes:
        error_msg = {"Error": "Only JSON is supported as returned content type"}
        return (error_msg, 406)
    # create new product
    if request.method == 'POST':
        request_content = json.loads(request.data) or {}
        new_product = add_product(request_content)#, owner_id)
        if isinstance(new_product, tuple):
            return new_product
        product_id = str(new_product.key.id)
        new_product["id"] = product_id
        new_product["self"] = request.base_url + '/' + product_id
        return Response(json.dumps(new_product), status=201, mimetype='application/json')

    #view user's products
    elif request.method == 'GET':
        product_list = get_all_products(request)#, owner_id)
        return Response(json.dumps(product_list), status=200, mimetype='application/json')

    # invalid action - edit/delete all products
    elif request.method == 'PUT' or request.method == 'DELETE':
        res = make_response('')
        res.headers.set('Allow', 'GET, PUT')
        res.status_code = 405
        return res
    else:
        return 'Method not recogonized'


