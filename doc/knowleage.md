# Objected knowleadge base, a specialized implemention for emails
## Vectorized Knowledge 
Large language models are trained on general corpora and without fine-tuning on user-specific data, they struggle to utilize user-related context effectively.

Users accumulate a vast amount of content that reflects their personality during their regular internet usage. This includes personal photos, tweets, Facebook posts, emails, etc. While it's possible to include all this content in the prompt during each interaction with the large language model, this approach is costly and can easily reach the token limit.

A common solution is to generate feature vectors from this content using word embedding techniques and store them in a vector database. During an interaction, the vector that is most relevant to the prompt is retrieved from the database, merged with the prompt, and then passed to the large language model.

We refer to this vectorized content as "knowledge". 

## Objected knownleadge base
In a personal AI system, to build a user's own knowledge base, we first need to implement various spider programs to crawl and retrieve all user-related data. Modern web content is typically rich text, including text, images, videos, hyperlinks, etc. Organizing this rich text in a tree-like structure similar to HTML is necessary, hence the need to introduce an object structure to represent this content.

Different parts of this content cannot be vectorized using the same embedding model. For instance, text and images, as well as the content of an image and its EXIF information, need separate embeddings. This means that in the vector database, the same content may have multiple vector values, and a row can represent a whole content item or just a part of it.

We need a comprehensive object structure to represent the hierarchy and relationships of content, as well as to implement the indexing and storage of objects. In the Minimum Viable Product (MVP) version, we'll implement a specialized solution for email content. In future versions, we can generalize this to handle other types of content, such as Facebook posts, tweets, etc.

## Agent with knowleadge base 
At the same time, we also need to explore the paradigm of using the knowledge base in Agents and workflows, so that the agent can better complete tasks in interaction with users through the context provided by the knowledge base.

