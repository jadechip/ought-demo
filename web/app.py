import os
import sys
import json
import hashlib
import requests
from itertools import islice
from elasticsearch import Elasticsearch
from flask import Flask, jsonify, render_template, request

import openai, numpy as np
from openai.embeddings_utils import get_embedding, cosine_similarity

api_key = os.environ['OPENAI_API_KEY']
openai.api_key = api_key

# rct_api_host = os.environ['RCT_API_URL']

# Elasticsearch config
es_host = os.environ['ELASTICSEARCH_URL']
print('Elastic host is {}'.format(es_host))
es = Elasticsearch([es_host])

if es.ping():
    print('Connected to ElasticSearch')
    # mappings = {
    #         "properties": {
    #             "title": {"type": "text"},
    #             "abstract": {"type": "text"},
    #             "authorNames": {"type": "text"}, # ES does not have an array field 
    #             "publicationYear": {"type": "integer"},
    #             "doi": {"type": "text"},
    #             "citedByCount": {"type": "integer"},
    #             "rctScore": {"type": "float"}
    #     }
    # }
    # es.indices.create(index="papers", mappings=mappings)
else:
    print('Could not connect to ElasticSearch')
    sys.exit()

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
     return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query')
    res = []
    if query != "":
        query_body = {
            "query": {
                "match": {
                    "title": query
                }
            }
        }
        res = es.search(index="papers", body=query_body)            
    else:
        res = es.search(index="papers", query={"match_all": {}})
    print("Got %d Hits:" % res['hits']['total']['value'])
    response = json.dumps(res['hits']['hits'], indent=2)
    return response

@app.route('/process-data', methods=['GET'])
def process_data(num_lines=1000):
    process_openalex(num_lines)
    process_s2ag(num_lines)
    return "<h1>Success</h1>"

@app.route('/similarity-score', methods=['GET'])
def similarity_score(doi='10.7717/peerj.4375'):

    paper_openalex = get_json(f'https://api.openalex.org/works/https://doi.org/{doi}')
    paper_s2ag = get_json(f'https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,abstract,citationCount,authors,publicationDate')

    if paper_openalex['abstract_inverted_index'] == '' or 'abstract' not in paper_s2ag:
        return

    # OpenAlex does not store the abstract as plaintext so we need to convert it
    abstract_alpha = reverse_inverted_index(paper_openalex['abstract_inverted_index'])    
    abstract_beta = paper_s2ag['abstract']
    
    # Calculate Semantic Similarity
    similarity_score(get_embedding(abstract_alpha), get_embedding(abstract_beta))

    # TODO: Add title and abstract from selected paper
    rct_score = 5.880430138108797 # post_json(rct_api_host, json={'title_abstract_pairs', '["This is a title", "This is an abstract"]'})
    print(rct_score)

    jsonify(rctScore=rct_score)
    
def process_openalex(num_lines):
    filename = 'data/openalex-sample.jsonl'
    with open(filename, 'r') as f:
        # Use a generator to prevent loading entire file into memory
        lines_gen = islice(f, num_lines)
        for i, line in enumerate(lines_gen):
            parsed_object = json.loads(line)
            if parsed_object['abstract_inverted_index'] is None or parsed_object['authorships'] is []:  # Skip records without an "Abstract" or any authors
                continue
            parsed_object['source'] = 'openalex'
            doc = create_mappings(parsed_object)
            # Unique id based on hash of title and abstract to prevent duplication
            hashval = gen_hash(doc["title"] + doc["abstract"])
            es.index(index="papers", id=hashval, document=doc)

def process_s2ag(num_lines):
    with open('data/s2ag-abstracts-sample.jsonl', 'r') as a, open('data/s2ag-papers-sample.jsonl', 'r') as b:
        # Use a generator to prevent loading entire file into memory
        abstracts_lines_gen = islice(a, num_lines)
        papers_lines_gen = islice(b, num_lines)

        for i, (x, y) in enumerate(zip(abstracts_lines_gen, papers_lines_gen)):
            parsed_x = json.loads(x)
            parsed_y = json.loads(y)
            if parsed_x['abstract'] is None: # Skip records without an "Abstract"
                continue
            parsed_y['source'] = 's2ag'
            parsed_y['abstract'] = parsed_x['abstract']
            doc = create_mappings(parsed_y)
            hashval = gen_hash(doc["title"] + doc["abstract"])
            es.index(index="papers", id=hashval, document=doc)
           
def create_mappings(object):
    if object['source'] == 'openalex':
        return {
            "title": object["title"],
            "abstract": reverse_inverted_index(object['abstract_inverted_index']),
            "authorNames": [x['author']['display_name'] for x in object['authorships']],
            "publicationYear": object["publication_year"],
            "doi": object["doi"],
            "citedByCount": object["cited_by_count"],
            "rctScore": 5.880430138108797 # post_json(rct_api_host, json={'title_abstract_pairs', '["This is a title", "This is an abstract"]'})
        }
    elif object['source'] == 's2ag':
        return {
            "title": object["title"],
            "abstract": object['abstract'],
            "authorNames": [author['name'] for author in object['authors']],
            "publicationYear": object["year"],
            "doi": object["externalids"]["DOI"],
            "citedByCount": object["citationcount"],
            "rctScore": 5.880430138108797 # post_json(rct_api_host, json={'title_abstract_pairs', '["This is a title", "This is an abstract"]'})        
        }

def gen_hash(key):
     return hashlib.md5(key.encode('utf-8')).digest()

def get_embedding(text, model="text-embedding-ada-002"):
   text = text.replace("\n", " ")
   return openai.Embedding.create(input = [text], model=model)['data'][0]['embedding']

def similarity_score(x, y):
    score = cosine_similarity(x, y)
    print('The score')
    print(score)
    return score

def reverse_inverted_index(index):
    word_index = []
    for k,v in index.items(): 
        for index in v: word_index.append([k, index])
        word_index = sorted(word_index, key = lambda x : x[1])
    word_index = [item[0] for item in word_index]
    abstract = " ".join(word_index)
    return abstract

def get_json(url):
    response = requests.get(url)
    return response.json()

def post_json(url, data):
    response = requests.post(url, json=data)
    return response.json()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')