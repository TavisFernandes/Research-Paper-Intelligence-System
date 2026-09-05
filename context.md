# Research Paper Intelligence & Comparison System

## 1. Project Overview

The project is an NLP-based system that accepts multiple research papers, processes and structures their content, extracts useful research information, creates semantic representations, retrieves relevant information, summarizes documents, answers questions, compares papers, and generates overall research insights.

Core idea:

Multiple Research Papers
-> Process and Understand Each Paper
-> Represent and Retrieve Information
-> Analyze Individual Papers
-> Compare Papers
-> Aggregate Research Insights

## 2. Main Objective

The system aims to reduce the effort required to understand and compare research papers.

Instead of treating a paper as one large block of text, the system should preserve:

Paper -> Page -> Section -> Chunk

The intended outputs include:

- Individual paper analysis
- Executive summaries
- Important keywords/entities
- Research information extraction
- Semantic search
- Paper Q&A
- Pairwise paper comparison
- Multi-paper research insights

## 3. Major Project Features

### Multi-Paper Input
- Upload multiple research papers.
- Assign a unique ID to each paper.
- Process a collection of papers related to a research topic.

### PDF Processing
- Extract text from normal PDFs.
- Detect scanned/image-based pages.
- Use OCR when necessary.
- Preserve page numbers and source information.

### NLP Processing
- Text cleaning
- Sentence segmentation
- Tokenization
- Lemmatization
- Section identification
- Paragraph/chunk creation

### Research Information Extraction

Eventually extract or generate:

- Title
- Authors
- Year
- Research problem
- Objective
- Methodology
- Dataset
- Models/algorithms
- Evaluation metrics
- Results
- Key findings
- Limitations
- Future work
- Keywords
- Named entities

### Keyword and Entity Analysis

Potential techniques:

- TF-IDF
- NER
- Frequency analysis

### Semantic Representation

Meaningful chunks will eventually be converted into vector representations.

A candidate semantic embedding model currently being evaluated is:

BAAI/BGE-M3

BGE-M3 is intended for semantic representation, similarity and retrieval.

### Vector Retrieval

Candidate vector databases currently being evaluated include:

- ChromaDB
- Other alternatives if required

The vector store should preserve:

Paper -> Page -> Section -> Chunk

### Long-Document Summarization

Because research papers are long documents, a candidate model being evaluated for summarization is:

LED (Longformer Encoder-Decoder)

The summarization component is intended to generate summaries from research papers or major sections.

The project should eventually support evaluation of generated summaries using:

- ROUGE-1
- ROUGE-2
- ROUGE-L

The exact summarization model and evaluation setup are still subject to experimentation.

### Question Answering / Semantic Search

Users should eventually be able to ask questions across uploaded papers and receive an answer with paper, section, page, and supporting evidence.

### Pairwise Comparison

Compare every selected pair of papers across research problem, objective, methodology, dataset, models, algorithms, metrics, results, findings, limitations, future work, and semantic similarity. Identify similarities, differences, and unique approaches.

### Multi-Paper Research Insights

Aggregate similarity matrices, common methodologies, datasets, models, metrics, performance comparisons, limitations, recurring problems, trends, and overall findings.

## 4. High-Level Project Flow

MULTIPLE RESEARCH PAPERS
-> PDF PROCESSING / OCR
-> TEXT EXTRACTION
-> NLP PREPROCESSING
-> SECTION IDENTIFICATION
-> CHUNKING
-> INDIVIDUAL PAPER ANALYSIS
-> NLP ANALYSIS / EMBEDDINGS / SUMMARIZATION
-> RETRIEVAL / ANALYSIS
-> Q&A / COMPARISON / SEARCH
-> PAIRWISE ANALYSIS
-> MULTI-PAPER ANALYSIS
-> RESEARCH INSIGHTS
-> UI

## 5. Important Architectural Principle

Embeddings and the LLM/summarization model have different roles.

Text Chunk
-> Embedding Model
-> Vector Representation
-> Vector Store
-> Retrieval of relevant original text
-> Relevant Text + Metadata
-> Generation Model / LLM

Vectors are used primarily for semantic retrieval and comparison. Generation and summarization operate on text/context.

## 6. Summary Evaluation

A human/reference summary is required for ROUGE evaluation. Metrics under consideration are ROUGE-1, ROUGE-2, and ROUGE-L. The evaluation dataset and reference-summary strategy remain subject to experimentation.

## 7. Backend Development Phases

1. PDF Processing & Document Understanding
2. NLP Analysis & Information Extraction
3. Semantic Embeddings & Vector Retrieval
4. Summarization and Summary Evaluation
5. Question Answering / RAG
6. Pairwise Paper Comparison
7. Multi-Paper Research Insights
8. Frontend-backend integration and testing

## 8. Current Backend Module

The first backend module is **PDF Processing & Document Understanding**.

Scope:

PDF input -> page-level extraction -> OCR fallback -> raw text preservation -> cleaning -> sentence segmentation -> tokenization -> lemmatization -> section identification -> chunk creation -> structured output.

This module must not implement later modules.

## 9. Data Contract

Paper:

- paper_id
- filename
- total_pages
- pages
- sections
- chunks

Page:

- paper_id
- page_number
- extraction_method
- raw_text
- cleaned_text

Section:

- paper_id
- section_name
- page_start
- page_end
- text

Chunk:

- paper_id
- chunk_id
- section_name
- page_start
- page_end
- text

Future modules should consume this structure rather than depending on internal PDF-processing implementation details.

## 10. Technology Status

The overall technology stack is **NOT FINALIZED**. PDF and OCR libraries, preprocessing strategy, embeddings, vector databases, summarization models, LLMs, and evaluation methods are under evaluation. Technologies used experimentally must be recorded as Experimental / Provisional until explicit team approval.

## 11. Team Collaboration

The backend is being developed by multiple team members independently. Keep modules separated, use stable interfaces and standardized data contracts, avoid unnecessary modification of other modules, and minimize merge conflicts.
