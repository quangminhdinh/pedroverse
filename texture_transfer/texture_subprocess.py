import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  
import warnings
warnings.filterwarnings('ignore', category=UserWarning)
import tensorflow as tf
import numpy as np
import sys
from PIL import Image


def run_style_predict(preprocessed_style_image, style_predict_path):
  # Load the model.
  interpreter = tf.lite.Interpreter(model_path=style_predict_path)

  # Set model input.
  interpreter.allocate_tensors()
  input_details = interpreter.get_input_details()
  interpreter.set_tensor(input_details[0]["index"], preprocessed_style_image)

  # Calculate style bottleneck.
  interpreter.invoke()
  style_bottleneck = interpreter.tensor(
      interpreter.get_output_details()[0]["index"]
      )()

  return style_bottleneck

def run_style_transform(style_bottleneck, preprocessed_content_image, content_image_size, style_transform_path):
  # Load the model.
  interpreter = tf.lite.Interpreter(model_path=style_transform_path)

  # Set model input.
  input_details = interpreter.get_input_details()
  for index in range(len(input_details)):
    if input_details[index]["name"]=='content_image':
      index = input_details[index]["index"]
      interpreter.resize_tensor_input(index, [1, content_image_size, content_image_size, 3])
  interpreter.allocate_tensors()

  # Set model inputs.
  for index in range(len(input_details)):
    if input_details[index]["name"]=='Conv/BiasAdd':
      interpreter.set_tensor(input_details[index]["index"], style_bottleneck)
    elif input_details[index]["name"]=='content_image':
      interpreter.set_tensor(input_details[index]["index"], preprocessed_content_image)
  interpreter.invoke()

  # Transform content image.
  stylized_image = interpreter.tensor(
      interpreter.get_output_details()[0]["index"]
      )()

  return stylized_image

def tensor_to_image(tensor):
    tensor = tensor*255
    tensor = np.array(tensor, dtype=np.uint8)
    if np.ndim(tensor)>3:
        assert tensor.shape[0] == 1
        tensor = tensor[0]
    return tensor

def load_img(path_to_img):
  img = tf.io.read_file(path_to_img)
  img = tf.io.decode_image(img, channels=3)
  img = tf.image.convert_image_dtype(img, tf.float32)
  img = img[tf.newaxis, :]

  return img

def preprocess_image(image, target_dim):
  # Resize the image so that the shorter dimension becomes 256px.
  shape = tf.cast(tf.shape(image)[1:-1], tf.float32)
  short_dim = min(shape)
  scale = target_dim / short_dim
  new_shape = tf.cast(shape * scale, tf.int32)
  image = tf.image.resize(image, new_shape)

  # Central crop the image.
  image = tf.image.resize_with_crop_or_pad(image, target_dim, target_dim)

  return image

def texture(content_img_path, blending_ratio, content_image_size, style_predict_path, style_transform_path, style_img_path, output_path):
    content_img = load_img(content_img_path)
    
    style_img = load_img(style_img_path)
                
    prev = preprocess_image(content_img, 256)
    content_img = preprocess_image(content_img, content_image_size)
    style_img = preprocess_image(style_img, 256)
    
    style_bottleneck_content = run_style_predict(
        prev, style_predict_path
    )
    style_bottleneck = run_style_predict(tf.constant(style_img), style_predict_path)
    style_bottleneck_blended = (blending_ratio/100.0) * style_bottleneck_content \
                    + (1 - (blending_ratio/100.0)) * style_bottleneck
    stylized_img = run_style_transform(style_bottleneck_blended, content_img, content_image_size, style_transform_path)
    stylized_img = tensor_to_image(stylized_img)
    Image.fromarray(stylized_img).save(output_path)

    print(output_path)



if __name__=="__main__":
    img_path = sys.argv[1]
    blending_ratio = float(sys.argv[2])
    content_image_size = int(sys.argv[3])
    style_predict_path = sys.argv[4]
    style_transform_path = sys.argv[5]
    filepath = sys.argv[6]
    output_path = sys.argv[7]
    texture(img_path, blending_ratio, content_image_size, style_predict_path, style_transform_path, filepath, output_path)