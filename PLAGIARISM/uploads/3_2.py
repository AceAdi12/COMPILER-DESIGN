from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

code1 = "print('Hello World')"
code2 = "print('Hello')"

vectorizer = TfidfVectorizer().fit_transform([code1, code2])
similarity = cosine_similarity(vectorizer[0:1], vectorizer[1:2])
print(f"Similarity: {similarity[0][0]*100:.2f}%")
