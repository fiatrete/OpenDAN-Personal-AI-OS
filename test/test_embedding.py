import sys
import os
import logging
from sentence_transformers import SentenceTransformer, util


dir_path = os.path.dirname(os.path.realpath(__file__))
print(dir_path)

sys.path.append("{}/../src/".format(dir_path))
print(sys.path)

root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
root.addHandler(handler)


def test_st():
    image_model = SentenceTransformer('clip-ViT-B-32-multilingual-v1')
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Our sentences we like to encode
    sentences = [
        "This framework generates embeddings for each input sentence",
        "Sentences are passed as a list of string.",
        "The quick brown fox jumps over the lazy dog.",
    ]

    # Sentences are encoded by calling model.encode()
    sentence_embeddings = model.encode(sentences)

    # Print the embeddings
    for sentence, embedding in zip(sentences, sentence_embeddings):
        print("Sentence:", sentence)
        print("Embedding:", embedding)
        print("")

    # Single list of sentences

    """
    sentences = [
        "The cat sits outside",
        "A man is playing guitar",
        "I love pasta",
        "The new movie is awesome",
        "The cat plays in the garden",
        "A woman watches TV",
        "The new movie is so great",
        "Do you like pizza?",
    ]
    """
    sentences = [
        "猫坐在外面",
        "狗坐在上面",
        "狗坐在里面",
        "一个男人在弹吉他",
        "我爱意大利面",
        "新电影太精彩了",
        "猫在花园里玩耍",
        "一个女人在看电视",
        "新电影太棒了",
        "你喜欢披萨吗？",
    ]

    # Compute embeddings
    embeddings = model.encode(sentences, convert_to_tensor=True)

    # Compute cosine-similarities for each sentence with each other sentence
    cosine_scores = util.cos_sim(embeddings, embeddings)

    # Find the pairs with the highest cosine similarity scores
    pairs = []
    for i in range(len(cosine_scores) - 1):
        for j in range(i + 1, len(cosine_scores)):
            pairs.append({"index": [i, j], "score": cosine_scores[i][j]})

    # Sort scores in decreasing order
    pairs = sorted(pairs, key=lambda x: x["score"], reverse=True)

    for pair in pairs[0:10]:
        i, j = pair["index"]
        print(
            "{} \t\t {} \t\t Score: {:.4f}".format(
                sentences[i], sentences[j], pair["score"]
            )
        )


if __name__ == "__main__":
    test_st()
