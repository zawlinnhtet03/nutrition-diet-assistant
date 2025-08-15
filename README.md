# NutriBench: Smart Nutrition and Diet Assistant

## Overview

NutriBench is a Streamlit-based web application that serves as a comprehensive nutrition and diet assistant. The application provides users with AI-powered nutrition advice, meal analysis capabilities, nutrition tracking dashboards, and report generation features. The system is designed with a modular architecture that separates authentication, database operations, and utility functions for maintainability and scalability.

# 📊 KB Nutrition Project – Datasets

This document lists curated datasets for building **food image recognition** and **nutritional analysis** systems. The datasets are categorized based on whether they contain nutritional annotations, general food recognition images, or specialized 3D/volume estimation data.

---

## 🍎 Datasets for Food Image Recognition **with Nutritional Analysis**

These datasets contain both food images and detailed nutritional metadata, making them ideal for end-to-end training.

| Dataset | Description | Link |
|---------|-------------|------|
| **Nutrition5k** | 5,000 top-down food images with detailed nutritional info (calories, protein, fats, etc.) across diverse food types and lighting conditions. | [GitHub – Nutrition5k](https://github.com/google-research-datasets/Nutrition5k) |
| **ChinaMartFood109** | 100,000+ images of 109 Chinese food categories with detailed nutritional annotations. Useful for cuisine-specific analysis. | [GitHub – ChinaMartFood109](https://github.com/paperswithcode/paperswithcode-data?tab=readme-ov-file) |

---

## 🥗 Datasets for General Food Image Recognition

These datasets are valuable for training models to **identify food items**, which can then be linked to an external nutrition database.

| Dataset | Description | Link |
|---------|-------------|------|
| **Food-101** | Benchmark dataset with 101 food categories; ideal for broad food classification tasks. | [Kaggle – Food-101](https://www.kaggle.com/datasets/dansbecker/food-101) |
| **Food2K** | Large-scale dataset with 2,000 categories and 1M+ images for fine-grained food recognition. | [GitHub – Food2K](https://github.com/paperswithcode/paperswithcode-data) |

---

## 🧪 Specialized Datasets for Portion Size & 3D Analysis

These datasets support **volume estimation** and **portion size calculation**, which are critical for accurate nutritional estimation.

| Dataset | Description | Link |
|---------|-------------|------|
| **MetaFood3D** | 3D models and point clouds of food items for portion size estimation. | [MetaFood3D – Paper PDF](https://arxiv.org/pdf/2409.01966) |
| **NutritionVerse3D** | 3D food dataset for volume and portion estimation tasks. | [Kaggle – NutritionVerse3D](https://www.kaggle.com/datasets/amytai/nutritionverse-3d) |

---

## 📌 Notes

- Start with **Food-101** or **Food2K** for general classification, then fine-tune with **Nutrition5k** or **ChinaMartFood109** for nutritional analysis.
- Use **MetaFood3D** / **NutritionVerse3D** if your application requires **portion estimation**.
- Combining datasets and linking results to a **nutrition knowledge base** will yield more accurate predictions.

---
