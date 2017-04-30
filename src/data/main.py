import json, os
from gensim.models.doc2vec import TaggedDocument, Doc2Vec
import csv
import pandas as pd
import glob
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import StratifiedShuffleSplit
import lightgbm as lgb
from sklearn.metrics import log_loss, accuracy_score, precision_recall_fscore_support
from sklearn.preprocessing import LabelEncoder
import random

print("### Reading data...")
f = open("data.json", "r")
data = json.load(f)

real_count = 0
fake_count = 0

documents = []

#print("Labeling documents...")
#for e in data:
#	document = e["text"]
#	_class = e["class"]
#	words = [w.strip() for w in document.split()]
#	if _class == "Fake":
#		documents.append(TaggedDocument(words=words, tags=["FAKE_" + str(fake_count)]))
#		fake_count += 1
#	else:
#		documents.append(TaggedDocument(words=words, tags=["REAL_" + str(real_count)]))
#		real_count += 1

text = []
_class = []
for e in data:
	text.append(e["text"])
	_class.append(e["class"])

df = pd.DataFrame({"text":text, "class":_class})

# Read the Kaggle dataset
print("### Reading Kaggle data...")
kaggle_df = pd.DataFrame.from_csv("kaggle-fake-news.csv")

print("Original data shape: " + str(df.shape))
df_real = df[df["class"] == "Real"]
df_fake = df[df["class"] == "Fake"]
print("Real count = " + str(df_real.shape[0]))
print("Fake count = " + str(df_fake.shape[0]))


print("Kaggle df shape: " + str(kaggle_df.shape))
df = df.append(kaggle_df)
print("Combined df shape: " + str(df.shape))

print("### Reading in BBC data...")
bbc_articles = []
## Reading in BBC dataset
bbc_categories = os.listdir("./bbc/")
for category in bbc_categories:
	filenames = os.listdir("./bbc/" + category)
	for fn in filenames:
		with open("./bbc/" + category + "/" + fn, "r") as f:
			lines = []
			for line in f:
				lines.append(line)
			bbc_articles.append(" ".join(lines))

bbc_df = pd.DataFrame({"text":bbc_articles})
bbc_df["class"] = "Real"

df = df.append(bbc_df)
print("Combined df shape with BBC data: " + str(df.shape))

df_real = df[df["class"] == "Real"]
df_fake = df[df["class"] == "Fake"]
print("Real count = " + str(df_real.shape[0]))
print("Fake count = " + str(df_fake.shape[0]))

### Add the NYTimes data here
NYTdocs = []
NYTfiles = glob.glob("./NYTdata/NYTstories_*")
for fname in NYTfiles:
	with open(fname, "r") as f:
		for line in f:
			art = json.loads(line)
			NYTdocs.append(art["text"])

NYTdf = pd.DataFrame({"text":NYTdocs})
NYTdf["class"] = "Real"

df = df.append(NYTdf)
print("Final total number of rows: " + str(df.shape[0]))
df_real = df[df["class"] == "Real"]
df_fake = df[df["class"] == "Fake"]
print("Real count = " + str(df_real.shape[0]))
print("Fake count = " + str(df_fake.shape[0]))


print("### Writing combined dataframe...")
df.to_csv("output.csv", index=False)
#exit(1)


## Random data learning verification
#df = df[df["class"] == "Fake"]
#idx = random.sample(df.index, len(df.index)/2)
#df.loc[idx, "class"] = "Real"

############################ Models ###############################

def vectorize(df, method='tfidf', n_features=250):
	if method == 'tfidf':
		corpus = df["text"].values.astype('U')
		tfidf = TfidfVectorizer(input='content', strip_accents='ascii', ngram_range=(1, 1), stop_words='english', max_features=n_features, norm="l2")
		print("### Fitting tfidf model...")
		tfidf.fit(corpus)
		print("### Transforming articles...")
		data = tfidf.transform(corpus)

		df_out = pd.DataFrame(data.todense())
		df_out["class"] = df["class"].values

	elif method == 'bow' or method == 'ngrams':
                corpus = df["text"].values.astype('U')
		if method == 'tfidf':
                        ngram_range = (1, 1)
                else:
                        ngram_range = (2, 2)
		bow = CountVectorizer(input='content', strip_accents='ascii', ngram_range=ngram_range, stop_words='english', max_features=n_features)
		print("### Fitting BoW model...")
                bow.fit(corpus)
                print("### Transforming articles...")
                data = bow.transform(corpus)

                df_out = pd.DataFrame(data.todense())
                df_out["class"] = df["class"].values
	elif method == 'doc2vec':
		pass

	return df_out

print("### Vectorization started...")
df_features = vectorize(df, method='tfidf')
ss = StratifiedShuffleSplit(n_splits=4, test_size = 0.25)

for train_idx, test_idx in ss.split(df_features, df_features["class"].values):
	train_df = df_features.iloc[train_idx]
	test_df = df_features.iloc[test_idx]

	train_Y = train_df["class"].values
	train_X = train_df.drop('class', axis=1).values

	le = LabelEncoder()
	le.fit(train_Y)
	if le.classes_[0] == "Fake":
		pos_label = 0
	else:
		pos_label = 1

	train_Y = le.transform(train_Y)

	val_Y = test_df['class'].values
	val_X = test_df.drop('class', axis=1).values
	val_Y = le.transform(val_Y)

	model = lgb.LGBMClassifier(boosting_type='gbdt', objective='binary', num_leaves=60, max_depth=5, learning_rate=0.01, n_estimators=200, subsample=1, colsample_bytree=0.8, reg_lambda=0)
	model.fit(train_X, train_Y, eval_set=[(val_X, val_Y)], eval_metric='logloss', early_stopping_rounds=20)

        val_preds_proba = model.predict_proba(val_X)
        loss = log_loss(val_Y, val_preds_proba)

	val_preds = model.predict(val_X)
	print(accuracy_score(val_Y, val_preds))
	print(precision_recall_fscore_support(val_Y, val_preds, pos_label = pos_label, average='binary'))

	print("Validation log_loss: " + str(loss))




###################################################################
if 0:
	real_tags = ["REAL_" + str(i) for i in range(0, real_count)]
	fake_tags = ["FAKE_" + str(i) for i in range(0, fake_count)]

	print("Done")

	print("Building model...")
	model = Doc2Vec(size = 100, alpha = 0.025, min_alpha=0.025)
	model.build_vocab(documents)
	print("Done")

	print("Training model...")
	for epoch in range(5):
		print("Iteration " + str(epoch) + " ...")
		model.train(documents)
		model.alpha -= 0.002
		model.min_alpha = model.alpha
	print("Done")

	fake_docs = [list(i) for i in model.docvecs[fake_tags]]
	real_docs = [list(i) for i in model.docvecs[real_tags]]

	for vec in fake_docs:
		vec.append("Fake")
	for vec in real_docs:
		vec.append("Real")

	docs = fake_docs + real_docs

	f = open("output.csv", "w")
	writer = csv.writer(f)
	writer.writerows(docs)
	f.close()