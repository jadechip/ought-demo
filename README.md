# Ought Demo Search Engine

## Running the demo locally

Run `build.sh` to spin up the containers using `docker-compose.yml`.

```
./build.sh
```

| URL                     | Service       |
|-------------------------|---------------|
| `http://localhost:9200` | Elasticsearch |
| `http://localhost:5601` | Kibana        |
| `http://localhost:5000` | Flask         |

Within other containers, Elasticsearch is accessed at `http://elasticsearch:9200`.

## API

`http://localhost:5000/` = Renders the main search HTML page.

`http://localhost:5000/search` = For making client-side requests to query the search engine.

`http://localhost:5000/process-data` = Preprocesses and ingests data from the provided datasets. **Please make sure to call this endpoint once to populate the database before using other endpoints.**

`http://localhost:5000/similarity-score` Calculates a similarity score between two documents.


## Overview

```
├── README.md
├── build.sh
├── docker-compose.yml
├── venv
│   ├── bin
│   ├── etc
│   ├── include
│   ├── lib
│   ├── pyvenv.cfg
│   └── share
└── web
    ├── Dockerfile
    ├── app.py
    ├── data
    │   ├── openalex-sample.jsonl
    │   ├── s2ag-abstracts-sample.jsonl
    │   └── s2ag-papers-sample.jsonl
    ├── requirements.txt
    └── templates
        └── index.html
```

As the core task was to create a search engine, I decided to go with ElasticSearch as it is fast, efficient, and scalable. 
Another potential alternative would be to use something like BigQuery but as the data is primarily json files, using a non-relational database schema made sense. 

For the purposes of this demo, I opted to use docker-compose to run multiple services locally. 
I used a simple Flask server to ingest and process data from two sample datasets downloaded from the OpenAlex and s2ag APIs.
Please see `web/app.py` for the relevant source code.

For the frontend, I used Jinja templating and xhr to display records and submit search queries for filtering.
Please see `web/templates/index.html` for the relevant source code.

### Deduplication

I opted to prevent duplicates by specifying a document identifier externally prior to indexing data into Elasticsearch. Specifically I used a numeric 128 bit MD5 hash based on the content of a given document, specifically the 'title' and 'abstract' fields. More information on this approach can be found here https://www.elastic.co/blog/efficient-duplicate-prevention-for-event-based-data-in-elasticsearch. 

I also implemented a more sophisticated method for more aggressive deduplication, by calculating a similarity score of two given records using embeddings and cosine_similarity. Although this method does incurr some addedd costs and might not be very scalable.


## Blockers

I wasn't able to pull the rct Docker image due to insufficient privileges, but I've added it to docker-compose and boilerplate code to easily include it in the future.

## Completion

### Level 0
- [x] Set up some appropriate tooling and infrastructure for this job
- [x] For purposes of this exercise, the infrastructure does not need to be “full size”, i.e., big enough to perform the job on the full datasets.
But it should be scalable in principle to handle the full datasets.
- [x] Document your choices

### Level 1
- [x] Denormalize the S2AG records to produce jsonlines records, one per paper, with the schema above (omit rctScore for now; it’s in Level 2).

### Level 2
- [ ] As part of the pipeline, enrich the data with scores representing the amount of “RCT-ness” in papers by their titles and abstracts; put this in rctScore.
These scores are provided via a containerized FastAPI service containing a trained model, with the image available at: public.ecr.aws/t9g4g7y2/rct-svm:latest
Sample response:

### Level 3
- [x] Combine S2AG data with OpenAlex data (https://docs.openalex.org/download-snapshot) (you only need to work with a small sample for purposes of this exercise).
DOIs are generally consistent across OpenAlex and S2AG data, so use these to reduce duplication of papers that are both in OpenAlex and S2AG.

### Level 4
- [ ] Each data source in fact contains many duplicate papers on their own, and not all have DOIs.
- [x] Add a method that will allow more aggressive entity resolution for papers. For example, if two papers have almost the same title and share authors, there should only be one of these in the final dataset.

Total time spent: approximately 7 hours.

## Examples

Please see examples of the working demo below:

Search returning all results, followed by results filtered by query:
<br>
![Alt text](./images/ought-demo-screengrab.gif "Search")

Ingested data, visualized in Kibana:
![Alt text](./images/es-screencap.jpg "Kibana")


