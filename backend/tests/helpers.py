"""Small PDF fixtures generated on the fly (no binary files committed)."""
from __future__ import annotations

from pathlib import Path

import pymupdf

PAPER_A = [
    ("Contrastive Retrieval for Scientific Papers",
     "Abstract\nWe study dense retrieval of scientific passages. We fine-tune BGE-M3 on the PubMedQA dataset and evaluate with Recall@10.\n"
     "1 Introduction\nResearch papers are long and hard to search. The problem is finding evidence quickly. We propose a retrieval system.\n"
     "2 Methods\nWe train the model with contrastive learning on PubMedQA. Hard negatives were mined using BM25.\n"
     "2.1 Negative sampling\nNegatives come from other abstracts."),
    (None,
     "3 Results\nThe fine-tuned model reaches Recall@10 of 0.91 compared with 0.84 for the baseline.\n"
     "4 Limitations\nOnly biomedical data was used in this study.\n"
     "5 Conclusion\nFine-tuning helps retrieval of scientific evidence.\n"
     "Future Work\nWe plan to test other domains such as physics.\n"
     "References\n[1] Smith et al. 2020. A paper."),
]
PAPER_B = [
    ("Image Classification with Convolutional Networks",
     "Abstract\nWe study image classification using a CNN trained on the CIFAR-10 dataset and report accuracy.\n"
     "1 Introduction\nImage recognition is a core problem in vision. We propose a compact convolutional network.\n"
     "2 Methods\nWe train a ResNet with data augmentation on CIFAR-10. Adam was used for optimisation."),
    (None,
     "3 Results\nThe network achieves accuracy of 95.1% on CIFAR-10.\n"
     "4 Conclusion\nCompact CNNs perform well. Future work will extend this to ImageNet."),
]


def make_pdf(path: Path, pages=PAPER_A) -> Path:
    doc = pymupdf.open()
    for title, body in pages:
        page = doc.new_page()
        y = 60
        if title:
            page.insert_text((72, y), title, fontsize=20)
            y += 40
        for line in body.split("\n"):
            page.insert_text((72, y), line, fontsize=10)
            y += 14
    doc.save(path)
    doc.close()
    return path


def make_scanned_pdf(path: Path) -> Path:
    """A PDF whose only page is an image of text (no text layer)."""
    source = pymupdf.open()
    page = source.new_page()
    page.insert_text((72, 100), "Scanned page content about retrieval", fontsize=24)
    pix = page.get_pixmap(dpi=100)
    source.close()
    doc = pymupdf.open()
    new = doc.new_page()
    new.insert_image(new.rect, pixmap=pix)
    doc.save(path)
    doc.close()
    return path


def make_blank_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    return path


def make_encrypted_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret text " * 20)
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="user", owner_pw="owner")
    doc.close()
    return path
