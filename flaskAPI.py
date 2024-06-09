from flask import Flask, jsonify, request
import xmlrpc.client
import mysql.connector
from elasticsearch import Elasticsearch
from datetime import datetime
import json

# Configuration Infos
# Odoo DB
ODOO_URL = 'http://odooInstance'
ODOO_DB = 'odooDBName'
ODOO_USERNAME = 'odooUser'
ODOO_PASSWORD = 'odooPWD'


# Wordpress DB
WP_DB_CONFIG = {
    'user': 'wordpressStore',
    'password': 'NCR1@Store',
    'host': '127.0.0.1',
    'database': 'wordpressDBStore'
}

# Elastisearch
ELASTICSEARCH_HOST = 'http://127.0.0.1:9200'
ELASTICSEARCH_INDEX = 'products'
ELASTICSEARCH_USERNAME = 'elastic'
ELASTICSEARCH_PASSWORD = 'NC1ElastP'

app = Flask(__name__)

# Setup Elasticsearch client with authentication
es = Elasticsearch(
    [ELASTICSEARCH_HOST],
    http_auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD)
)

def connect_to_odoo():
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(ODOO_URL))
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(ODOO_URL))
    return models, uid


def connect_to_wordpress():
    connection = mysql.connector.connect(**WP_DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    query = """
    SELECT 
        wp_posts.post_title AS name, 
        wp_postmeta.meta_value AS price, 
        wp_posts.post_modified AS updated_date 
    FROM 
        wp_posts 
    JOIN 
        wp_postmeta 
    ON 
        wp_posts.ID = wp_postmeta.post_id 
    WHERE 
        wp_postmeta.meta_key = '_price'
    """
    cursor.execute(query)
    products = cursor.fetchall()
    cursor.close()
    connection.close()
    return products
@app.route('/api/storeproducts', methods=['GET'])
def get_store_products():
    products = connect_to_wordpress()
    return jsonify(products)

@app.route('/api/products', methods=['GET'])
def get_products():
    models, uid = connect_to_odoo()
    products = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product',
                                 'search_read', [[]], {'fields': ['name', 'list_price']})
    return jsonify(products)
@app.route('/api/insert_elastic', methods=['POST'])
def insert_into_elastic():
    data = request.json
    actions_payload = ""
    current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')  # Generate timestamp

    for item in data:
        try:
            price = int(float(item['price']))
            #id = item.get('id')
            action = {
                "index": {
                    "_index": ELASTICSEARCH_INDEX,
                }
            }
            source = {
                "name": item['name'],
                "price": price,  # Ensure price is an integer
                "@timestamp": current_time
            }
            actions_payload += f"{json.dumps(action)}\n{json.dumps(source)}\n"
        except (ValueError, KeyError) as e:
            print(f"Skipping invalid item: {item} - {e}")

    response = es.bulk(body=actions_payload)
    if response.get('errors'):
        print("Failed to insert some or all data")
    else:
        print("Data inserted successfully")
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
