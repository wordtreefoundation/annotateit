
DATA_DIR=~/code/annotateit/data

# Start ElasticSearch
docker run -d --name elasticsearch \
           --publish 9200 \
           --publish 9300 \
           --volume $DATA_DIR:/data \
           dockerfile/elasticsearch \
           /elasticsearch/bin/elasticsearch \
           -Des.path.logs=/data \
           -Des.path.data=/data

# Start AnnotateIt
docker run -d --name annotateit \
		   --publish 5000 \
           --link elasticsearch:es \
           --volume $DATA_DIR:/data \
           wordtree/annotateit
