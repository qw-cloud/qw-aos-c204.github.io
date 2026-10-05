## Final Project: Automated Aircraft Detection in Satellite Imagery Using Deep Learning
Qingyang (Frank) Wu

Department of Environmental Health Science, UCLA

AOS C204: Introduction to Machine Learning for the Physical Sciences

Instructor: Dr. Alexander Lozinski

December 2024

***

## Introduction 

Satellite imagery provides insights across sectors, including agriculture, defense intelligence, energy, and financial services. The advancement of satellite imaging technology has generated an exponential increase in daily image acquisition, rendering manual analysis computationally intractable. This technological evolution necessitates the implementation of automated machine learning and computer vision algorithms for efficient processing and analysis of massive image datasets.
This investigation proposes a deep learning framework utilizing convolutional neural networks (CNNs) for automated aircraft detection and recognition in satellite imagery. The methodology supports airport monitoring, traffic flow analysis, and defense intelligence applications. The implementation demonstrates improvements in detection efficiency while  reducing manual monitoring costs, establishing a foundation for automated GIS analysis.

## Data

This investigation utilizes the ["Planes in Satellite Imagery"](https://www.kaggle.com/datasets/rhammell/planesnet/data) dataset, derived from [Planet Labs](https://www.planet.com/)' commercial satellite imagery, encompassing satellite captures over multiple airports in California, United States. The dataset comprises 32,000 RGB images, each sized at 20x20 pixels, categorized into binary classes: "plane" and "no-plane", facilitating machine learning model development for aircraft detection and localization in satellite imagery.
Dataset Composition:

**Positive Class (Aircraft Present):**

Sample size: 8,000 images

Characteristics: Aircraft fuselage centered in frame

Features: Distinct wing structures, tail assemblies, and nose sections

Variability: Multiple aircraft configurations, orientations, and atmospheric conditions

![image](https://github.com/user-attachments/assets/c4ec1408-b439-4c46-94e6-9ea5c1f5e8b3)
**Source**: ["Planes in Satellite Imagery"](https://www.kaggle.com/datasets/rhammell/planesnet/data)

**Negative Class (Aircraft Absent):**

Sample size: 24,000 images

Subcategories:

a) Complete absence of aircraft (terrain features, water bodies, vegetation, built structures)

b) Partial aircraft features

c) Misclassified instances due to high-intensity reflectance or linear terrain features


**Annotation Specifications:**

Binary classification labels (1: aircraft present, 0: aircraft absent)

Scene identifiers

Geocentric coordinates (latitude/longitude) for image centroids

**Validation Framework:**

Primary validation: Four complete satellite scenes provided within the dataset

Supplementary validation: Four independent airport scenes acquired through external sources for robustness assessment 

The dataset structure follows established principles in remote sensing research: 

The 1:3 class distribution ratio aligns with standard practices in computer vision for handling class imbalance
The image resolution and dimensionality correspond to optimal parameters identified in satellite-based object detection literature
The inclusion of diverse environmental conditions enhances model generalization capabilities

**Validation on Complete Scenes:**

While our models are trained on 20x20 patches, the goal is to detect planes in larger satellite scenes. To accomplish this, I apply a sliding window approach across each full-resolution satellite scene. Concretely, I shift a 20x20 window over the scene in small strides (e.g., 5 pixels), extract each patch, and feed it into the trained model for classification. Any patch that yields a probability above a chosen detection threshold (e.g., 0.5) is considered a detection. To reduce overlapping boxes, I apply non-maximum suppression (NMS) on these detection proposals, thereby merging adjacent bounding boxes into a single detection region.

This process is repeated for our primary validation scenes (four complete satellite images from the dataset) and for supplementary validation scenes (four new airport images) to measure real-world performance. I then count the number of correct detections (true positives), missed detections (false negatives), and false positives to calculate the overall accuracy, precision, and recall at the scene level. This approach ensures that although training occurs on small 20x20 samples, the final evaluation step simulates an actual detection workflow over full-scale imagery.

**Data Preprocessing and Annotation Usage:**

In this study, each raw satellite image is provided as three channels of pixel intensity (red, green, and blue). I normalize each channel by dividing by 255.0 to scale the pixel values into the range [0,1]. The processed dataset X is thus shaped as (𝑁,20,20,3), where N is the total number of samples (e.g., 32,000), and each 20x20 image contains 3 color channels.

I were also provided with additional annotation specifications, including scene identifiers and geocentric coordinates (latitude/longitude). For the classification and detection tasks in this report, only the binary labels (0 for no-plane, 1 for plane) were dwerectly utilized as the training targets. The coordinates and scene identifiers were retained in the metadata for possible cross-referencing and advanced analyses (for instance, mapping detections back to real-world coordinates), but they were not explicitly used as inputs to the deep learning models.

This preprocessing ensures that all models in subsequent sections receive uniformly scaled input images, facilitating stable and consistent model training.

![image](https://github.com/user-attachments/assets/037c60e2-a16e-4492-9311-04f408902bb3)
**Source**: ["Planes in Satellite Imagery"](https://www.kaggle.com/datasets/rhammell/planesnet/data)


## Preliminary Data Visualization


The top row of the first figure (with aircraft present) includes three heatmaps representing the mean red, green, and blue (RGB) values from 8,000 images containing aircraft. These heatmaps show higher RGB values concentrated in the center, with a distinct transition from red to yellow, indicating elevated RGB levels in central regions. This pattern arises because aircraft are generally positioned near the center, resulting in higher average RGB values in a cross-like shape. In contrast, the bottom row (without aircraft) displays heatmaps with a more uniform color distribution and smaller differences between the center and edges, reflecting the more consistent RGB distribution across the 24,000 aircraft-free images. In these images, overall RGB levels are lower, particularly within the red and green channels.

![rgb_analysis](https://github.com/user-attachments/assets/75105ec3-78cd-44a7-bc84-be447639cf11)

**Figure 1: Average RGB values**


**Model Initialization and Hyperparameter Tuning**

For each model, I initialized the hyperparameters either based on common best practices or through a brief tuning process on a smaller validation subset (e.g., 10% of the dataset). In particular:

- Logistic Regression: max_iter=1000, using standard L2 regularization.
- Random Forest: n_estimators=100, with Gini impurity, and a maximum depth set by the default or auto termination.
- XGBoost and LightGBM: n_estimators=100, max_depth=6, and learning_rate=0.1. I briefly experimented with learning rates {0.01, 0.1, 0.2} and found 0.1 to be optimal in balancing speed and accuracy.
- Support Vector Machine: Used an RBF kernel with default γ (scale), and I tested C values in {1, 10, 100} before choosing C=1 for the final run.
- Neural Networks (CNNs/ResNet): I employed an Adam optimizer with a fixed learning rate of 0.001, trained for 20 epochs and a batch size of 32. Basic CNN architectures started with 32 filters, then 64, etc., while the deeper architectures added dropout rates of 0.25 or 0.5. In the custom ResNet, I used 32 and 64 filters in each residual block.

I did not employ pre-trained Iights in these experiments because the input resolution (20x20) differs substantially from typical large-scale ImageNet training. Instead, all CNN-based models were trained from scratch. I performed manual hyperparameter tuning rather than a full grid or random search, given the relatively small image size and the computational cost.

**Modelling**

Initially, several classical algorithms were applied to the aircraft recognition task. A logistic regression model, set with a maximum of 1000 iterations, achieved an accuracy of 90.80%, though with a relatively long training time of 4.51 seconds. A random forest classifier, configured with 100 estimators and parallel computation enabled, demonstrated robust classification performance with an accuracy of 95.08% and a precision of 93.01%. The XGBoost model, also using 100 tree estimators, with a learning rate of 0.1 and a maximum depth of 6, performed best among traditional machine learning models, reaching an accuracy of 95.73% using histogram-based optimization. LightGBM, with parameters similar to XGBoost, achieved a comparable accuracy of 95.55%. The support vector machine (SVM) with an RBF kernel attained an accuracy of 95.72% but exhibited the longest training time, at 105.70 seconds. The k-nearest neighbors classifier, configured with 5 neighbors, yielded an accuracy of 94.75% and a recall of 91.60%. The decision tree and Naïve Bayes models achieved accuracies of 89.72% and 63.98%, respectively, with Naïve Bayes performing fastest (0.43 seconds) but less effectively overall.

![model_comparison_light](https://github.com/user-attachments/assets/720d8438-64f1-4582-ac63-d2c240b38ff0)
**Figure 2: Performance of Classic Machine Learning**

For deep learning models, three convolutional neural network (CNN) architectures were implemented and evaluated. The basic CNN model employed a simple design, comprising two convolutional layers (with 32 and 64 filters) combined with max pooling, followed by fully connected layers for output, achieving an accuracy of 97.02%, precision of 92.39%, and recall of 95.92%. A deeper CNN model, with a more complex architecture incorporating batch normalization and dropout layers (rates of 0.25 and 0.5), along with additional convolutional filters (64 and 128), reached an accuracy of 90.20% and a precision of 99.79%, though with a lower recall of 60.82%. The custom ResNet model, featuring residual connections and residual blocks with 32 and 64 filters, combined with batch normalization and global average pooling layers, achieved the best overall performance across all models, with an accuracy of 98.62%, precision of 97.36%, recall of 97.12%, and F1 score of 97.24%. All deep learning models used the Adam optimizer and binary cross-entropy loss function, training over 20 epochs with a batch size of 32 and a validation split of 0.2.

![model_comparison](https://github.com/user-attachments/assets/16063914-f2f8-4582-82c7-31891351d9ff)

**Figure 3: Performance of Deep Learning**

These experimental results clearly indicate that deep learning methods, particularly those incorporating residual connections, exhibit superior performance in this image recognition task. Although certain traditional machine learning methods (such as XGBoost and SVM) achieved relatively high performance, the deep learning models demonstrated enhanced feature extraction and classification capabilities, especially when considering accuracy, precision, and recall comprehensively.


## Results

The custom ResNet model demonstrated exceptional classification performance, as evidenced by its confusion matrix: true negatives (TN) totaled 23,796 (99.2%), true positives (TP) reached 7,665 (95.8%), false negatives (FN) were 335 (4.2%), and false positives (FP) remained low at 204 (0.9%). These results indicate high model accuracy in distinguishing positive and negative samples, with particularly strong control over the false positive rate.

![confusion_matrix_enhanced](https://github.com/user-attachments/assets/9c56290a-a76a-49ad-a760-d832e6237680)
**Figure 4: Confusion Matrix with ResNet**

The model’s classification strength is further highlighted by an area under the ROC curve (AUC) of 0.997, close to the ideal value of 1.0, demonstrating excellent discriminative ability. Additionally, the precision-recall (PR) curve yielded an average precision (AP) of 0.990, with a consistently high curve, indicating that the model sustains both high precision and high recall.

![image](https://github.com/user-attachments/assets/7111eb5a-eb7e-4604-9b08-20feb1cdd746)
**Figure 5: Performance Curves with ResNet**


The model's training history further supports its strong learning characteristics:

**Accuracy**: Training accuracy (solid blue line) steadily increased from an initial 0.93 to exceed 0.99, while validation accuracy (dashed blue line) showed some variability but generally maintained high values (between 0.85 and 0.98).

**Loss**: Training loss (solid red line) consistently decreased to a low level, while validation loss (dashed red line) displayed occasional fluctuations (notably around epochs 5 and 15) but trended favorably overall without signs of persistent overfitting.
![image](https://github.com/user-attachments/assets/f4949e50-213a-445a-a3fa-83231c701169)
**Figure 6: Training History with ResNet**

These metrics collectively suggest that the custom ResNet model achieved outstanding classification performance with robust generalization. While some fluctuation occurred during training, the model ultimately stabilized, achieving effective feature learning likely enhanced by the unique advantages of residual connections in handling image features.


Feature maps represent the activation outputs of convolutional layers, allowing analysis of feature extraction capabilities at each layer. 

To visualize the convolutional layers’ activation maps, I created an intermediate Keras model that outputs the feature maps from each convolutional layer. Concretely, I used:

```python
layer_outputs = [layer.output for layer in model.layers if isinstance(layer, tf.keras.layers.Conv2D)]
feature_model = tf.keras.models.Model(inputs=model.input, outputs=layer_outputs)
```

I then passed a single input image (e.g., an image from the test set) through feature_model.predict(), obtaining a stack of 2D feature maps for each convolutional layer. Each feature map was then normalized (e.g., min-max scaling) to enhance visibility and plotted using Matplotlib. Different layer depths reveal different hierarchical features, such as edges or textures in earlier layers and more abstract shapes in deeper layers.

Different colors correspond to activation value ranges, illustrating the network's response intensity to inputs at specific layers. With increasing convolutional layer depth, the complexity of feature extraction progressively intensifies:


**Conv Layer 1** captures simple edges and textures, highlighting local variations in the input.
![feature_maps_layer_1](https://github.com/user-attachments/assets/f085212b-038e-4185-ad33-df841d70b2d6)

**Conv Layers 2 to 5** depict blurred texture features, gradually expanding the receptive field to capture more intricate edge combinations and local structures.

![feature_maps_layer_2](https://github.com/user-attachments/assets/6a577527-670a-4b3b-9ee9-489402883155)
![feature_maps_layer_3](https://github.com/user-attachments/assets/774a30b3-3e1d-4289-9c9c-7e62551d7cc4)
![feature_maps_layer_4](https://github.com/user-attachments/assets/59970d90-2d8b-4bc9-a6fb-07d149526a57)
![feature_maps_layer_5](https://github.com/user-attachments/assets/ba552c5b-73b6-4196-96b5-2d325aa426a1)

**Conv Layers 6 to 8** show further blurring, reflecting the extraction of more abstract compositional patterns within the image.

![feature_maps_layer_6](https://github.com/user-attachments/assets/26e715b8-92e7-4c38-be27-4681f631fe01)
![feature_maps_layer_7](https://github.com/user-attachments/assets/052f51e2-6091-4075-a269-a145b7e84df4)
![feature_maps_layer_8](https://github.com/user-attachments/assets/bba7d621-8a2a-480a-afff-b5c61a5d7960)

**Conv Layer 9** exhibits dispersed activation patterns, enhancing the detection of higher-level shape features.

![feature_maps_layer_9](https://github.com/user-attachments/assets/2e488bf8-a9f0-4497-a0ec-a972a8bf6bc6)

**Conv Layer 10** reveals strong regional activations aimed at extracting global image features, which support the final classification.

![feature_maps_layer_10](https://github.com/user-attachments/assets/314069bf-3f57-4a1d-9926-4dadaeede071)

From lower to higher layers, the feature maps of ResNet illustrate the network's hierarchical abstraction, transitioning from spatial details to global pattern recognition. This progression highlights ResNet's mechanism of building from basic features to complex patterns, enabling robust image recognition.

**Figure 7: Feature Importantce 1-10 with ResNet**

## Discussion (Part 1)
In object detection across four scenarios, both a basic CNN and a ResNet were applied, with ResNet consistently producing fewer detection boxes than the CNN model. The CNN demonstrated a tendency toward generating a higher number of detections (with more false positives), while ResNet achieved more concise detections with higher confidence scores.

**Scenario 1: Airport Scene**

CNN Detection (Odd Image 1): The basic CNN model detected 150 targets, with detection boxes densely distributed, especially near the central area of the airport. Confidence scores varied widely from 0.30 to 1.00, and a high number of false positives appeared in complex textured areas, such as runways and tarmacs.

ResNet Detection (Even Image 2): The ResNet model identified 99 targets, significantly fewer than the CNN. ResNet exhibited a more conservative approach with fewer false positives, concentrating higher-confidence detections on prominent structures like tarmacs and airport buildings. This suggests ResNet’s advantage in extracting high-level features and filtering noise, with a focus on high-confidence targets. Thus, ResNet effectively handles complex structures and noise by concentrating on reliable features.

![basic_cnn_scene_1](https://github.com/user-attachments/assets/46f08cfe-bdc0-4e50-9648-3d5f7e581727)
![custom_resnet_scene_1](https://github.com/user-attachments/assets/a2f432d8-75e1-46fc-990d-a8461bb541d3)

**Scenario 2: Simplified Airport Scene**

CNN Detection (Odd Image 3): In this simplified scene, the CNN detected 45 targets, dispersed broadly with confidence scores ranging from 0.30 to 1.00. Many detections appeared around runways and ground structures, reflecting high sensitivity to large textured areas.

ResNet Detection (Even Image 4): ResNet detected only 28 targets, with confidence scores from 0.44 to 1.00, concentrating on significant structures like airport buildings and runways. This model effectively minimized false positives, confirming its superior ability to filter non-target areas in simpler environments. ResNet’s performance highlights its capacity to selectively respond to essential features, yielding a significantly lower false detection rate compared to CNN.

![basic_cnn_scene_2](https://github.com/user-attachments/assets/8d95075c-3c30-404b-a3f2-be3b9d6a4c37)
![custom_resnet_scene_2](https://github.com/user-attachments/assets/eafd2d46-ae57-48dc-b6f5-051e7992af02)

**Scenario 3: Complex Airport Traffic Area**

CNN Detection (Odd Image 5): The CNN identified 195 targets, the highest count among scenarios, underscoring its heightened sensitivity in complex settings. Detection boxes were spread across runways, tarmacs, and surrounding structures, with broad confidence levels (0.30 to 1.00). The model showed a strong response to edge features but also overproduced detection boxes.

ResNet Detection (Even Image 6): ResNet detected 119 targets, a substantial reduction from the CNN. Detection boxes were concentrated around runway edges and key buildings, with high-confidence detections (close to 1.00) in prominent regions. In this complex environment, ResNet effectively focused on critical features with fewer redundant detections, demonstrating its robust capability to manage intricate settings by selectively concentrating on distinct features.

![basic_cnn_scene_3](https://github.com/user-attachments/assets/381c2c21-d90b-4fed-a863-abbd7aed0505)
![custom_resnet_scene_3](https://github.com/user-attachments/assets/6525c1d5-657d-431b-8b41-41bd86556976)

**Scenario 4: Open Area with Few Buildings and Texture**

CNN Detection (Odd Image 7): In this open scene, the CNN detected 193 targets, with confidence scores ranging from 0.30 to 1.00. Detection boxes were predominantly centered around buildings, indicating high sensitivity to low-level features but also numerous redundant detections in low-texture areas.

ResNet Detection (Even Image 8): ResNet detected 165 targets, still high but fewer than CNN, with detection focused on buildings and prominent areas. Higher-confidence detections were more prevalent, and ResNet managed redundant detections effectively, indicating better adaptation to low-texture regions.

![basic_cnn_scene_4](https://github.com/user-attachments/assets/bee397bf-65a4-49e9-af8d-a525e9d16d00)
![custom_resnet_scene_4](https://github.com/user-attachments/assets/c936d25e-64a9-48b0-b5e7-cb4cb0a4414d)

**Figure 8: Scenario Verification With Basic CNN vs. Custom ResNet**


## Discussion (Part 2)

In analyzing the differences between the basic CNN and ResNet architectures on lower-quality aircraft images, notable variations emerge in detection count, confidence range, false positives, and spatial distribution across four scenes:


**Scene 1: Dense Aircraft Area on Tarmac**


CNN Detection (Odd Image 1): The CNN model detected 35 targets with densely clustered boxes around the aircraft and tarmac. Confidence scores ranged widely from 0.34 to 1.00, reflecting CNN’s sensitivity to low-level features, which led to multiple detections on aircraft components (e.g., wings, tails) and overlapping, redundant boxes. This suggests CNN’s tendency to misinterpret background details, producing overlapping detections.
ResNet Detection (Even Image 2): ResNet detected 14 targets, focusing detections on the primary aircraft bodies with high confidence (mostly 0.99 or 1.00). The model's attention to contour, structure, and spatial context minimized redundant boxes, indicating strong suppression of irrelevant background features and fewer false positives.

![basic_cnn_images](https://github.com/user-attachments/assets/d32589ac-4fda-40e1-b03d-3c4343c9063a)
![custom_resnet_images](https://github.com/user-attachments/assets/3292892b-d85e-4bd4-8225-d4e513989c4e)


**Scene 2: Aircraft and Hangar Area with Dense Parking**

CNN Detection (Odd Image 3): In this scene, CNN identified 40 targets, focusing on aircraft and tarmac with confidence scores from 0.30 to 1.00. Lower-confidence detections suggest CNN’s susceptibility to edges and textures, resulting in false positives due to small structural features on the tarmac. The model produced overlapping, low-confidence detections, driven by complex structural details.
ResNet Detection (Even Image 4): ResNet identified 28 targets, with boxes concentrated on key parts of each aircraft and confidence mostly above 0.70. Its ability to extract high-level features enabled ResNet to focus on main aircraft structures, avoiding low-confidence detections and significantly reducing overlap. This stability in complex backgrounds highlights ResNet’s effectiveness in maintaining robust detections without false positives.


![basic_cnn_images1](https://github.com/user-attachments/assets/5f0b48f7-d04f-49d3-82a0-8bb92d106de8)
![custom_resnet_images1](https://github.com/user-attachments/assets/c53b2408-e564-46bf-bd4e-852b18e50606)

**Scene 3: Highly Textured Tarmac with Multiple Aircraft**

CNN Detection (Odd Image 5): The CNN model detected 255 targets, saturating the tarmac area with detection boxes due to a highly textured scene with similar structural features (e.g., aircraft contours, tarmac edges). Confidence varied from 0.30 to 1.00, and the high false positive rate was especially evident around edges and shadows, where numerous low-confidence detections were generated.
ResNet Detection (Even Image 6): ResNet detected 126 targets, focusing primarily on aircraft bodies with minimal detections in the background. This model maintained high confidence (typically over 0.70), demonstrating more reliable detection of aircraft features and effective filtering of background noise in complex scenes. ResNet’s refined feature recognition capabilities allowed it to minimize false positives while concentrating on key targets.

![basic_cnn_images2](https://github.com/user-attachments/assets/65321903-b4c5-49aa-bae3-926af47d80f5)
![custom_resnet_images2](https://github.com/user-attachments/assets/771ce12b-1b8d-46dd-85ab-8baffbc22543)


**Scene 4: Multiple Aircraft in Simplified Background**

CNN Detection (Odd Image 7): In this simpler scene, CNN detected 24 targets with narrow confidence intervals (mostly 0.80 to 1.00), showing stable detection in low-complexity settings. However, minor overlapping detections were observed, especially around wings and tails, where CNN redundantly identified similar local features.
ResNet Detection (Even Image 8): ResNet detected only 8 targets, focusing solely on aircraft bodies with high confidence (all above 0.80), effectively avoiding overlap and redundant detections seen in CNN. With minimal background interference, ResNet maintained precise focus on each aircraft’s main features, avoiding duplicate detections and achieving high detection accuracy.

![basic_cnn_images3](https://github.com/user-attachments/assets/1e10c572-bd6e-4615-9b73-f7e674b5946e)
![custom_resnet_images3](https://github.com/user-attachments/assets/b9b3f65b-df92-4459-b841-e25036ec96ac)

**Figure 9: Additional Scenario Verification With Basic CNN vs. Custom ResNet**


The basic CNN model demonstrated heightened sensitivity to low-level features, effectively capturing edges and textures but often at the cost of increased false positives, especially in complex or high-frequency areas. While CNN performed adequately in simpler backgrounds, it struggled with edge control and noise suppression, leading to redundant and overlapping detections.

In contrast, ResNet’s residual block design minimized information loss, preserving critical features across deeper layers and enabling the model to capture high-level characteristics more effectively. This design allowed ResNet to maintain focus on core features, reduce false positives, and avoid redundant detections, particularly in complex or noisy scenes. Overall, ResNet proved more robust and stable across various scene complexities, excelling in well-defined areas and demonstrating superior adaptability for precise, high-confidence detection, particularly in challenging or lower-quality satellite imagery.

## Conclusion

The experimental results underscore the fundamental architectural differences between traditional machine learning methods and deep learning models, each displaying unique strengths and limitations. However, it is evident that the custom ResNet model consistently outperforms across both the test dataset and real-world validation, accurately identifying the majority of aircraft targets with a markedly lower false positive rate compared to the basic CNN model (He et al., 2016)[^1].

As similar architectures are considered for larger-scale or more complex satellite imagery, maintaining high performance while managing computational costs becomes crucial. Optimizing model structures for such applications will demand increased computational resources and training time. Residual neural networks represent a promising architecture, especially suited for tackling more sophisticated remote sensing detection tasks [^2]. Additionally, expanding the dataset to include a wider array of scene characteristics would be beneficial, as future research could extend to multi-object detection, enabling classification of various types of ground targets across different weather and terrain conditions. This expansion would further enhance model robustness and applicability in diverse remote sensing scenarios.

## References
[^1]: He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual learning for image recognition. In Proceedings of the IEEE conference on computer vision and pattern recognition (pp. 770-778).

[^2]:Xie, S., Girshick, R., Dollár, P., Tu, Z., & He, K. (2017). Aggregated residual transformations for deep neural networks. In Proceedings of the IEEE conference on computer vision and pattern recognition (pp. 1492-1500).
