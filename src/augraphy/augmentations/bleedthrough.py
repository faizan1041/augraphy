import numpy as np
import random
import cv2
from PIL import Image

from augraphy.base.augmentation import Augmentation
from augraphy.base.augmentationresult import AugmentationResult


class BleedThroughAugmentation():
    """Emulates bleed through effect from the combination of ink bleed and
    gaussian blur operations.

    :param intensity_range: Pair of floats determining the range from which
           noise intensity is sampled.
    :type intensity: tuple, optional
    :param color_range: Pair of ints determining the range from which color
           noise is sampled.
    :type color_range: tuple, optional
    :param ksize: Tuple of height/width pairs from which to sample the kernel
           size. Higher value increases the spreadness of bleeding effect.
    :type ksizes: tuple, optional
    :param sigmaX: Standard deviation of the kernel along the x-axis.
    :type sigmaX: float, optional
    :param alpha: Intensity of bleeding effect, recommended value range from
            0.1 to 0.5.
    :type alpha: float, optional
    :param offsets: Tuple of x and y offset pair to shift the bleed through 
            effect from original input.
    :type offsets: tuple, optional
    :param p: The probability this Augmentation will be applied.
    :type p: float, optional
    """
    def __init__(
        self,
        intensity_range=(0.1, 0.2), 
        color_range=(0, 224), 
        ksize = (17,17),
        sigmaX = 0,
        alpha = 0.3,
        offsets = (10,20),
        p=0.5
    ):
        super().__init__(p=p)
        self.intensity_range = intensity_range
        self.color_range = color_range
        self.ksize = ksize
        self.sigmaX  = sigmaX 
        self.alpha = alpha
        self.offsets = offsets

    # Constructs a string representation of this Augmentation.
    def __repr__(self):
        return f"BleedThroughAugmentation(intensity_range={self.intensity_range}, color_range={self.color_range}, ksize={self.ksize}, sigmaX={self.sigmaX},alpha={self.alpha},offsets={self.offsets},p={self.p})"
 
    # Add salt and pepper noise
    def add_sp_noise(self, img, prob=0.05):
        output = np.zeros_like(img)
        thres = 1 - prob 
        for i in range(img.shape[0]):
            for j in range(img.shape[1]):
                rdn = random.random()
                if rdn < prob:
                    output[i][j] = 255
                elif rdn > thres:
                    output[i][j] = 0
                else:
                    output[i][j] = img[i][j]
        return output
    
    # Computes the gradient of the image intensity function.
    def sobel(self, image):
        gradX = cv2.Sobel(image, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
        gradY = cv2.Sobel(image, ddepth=cv2.CV_32F, dx=0, dy=1, ksize=-1)
        gradient = cv2.subtract(gradX, gradY)
        gradient = cv2.convertScaleAbs(gradient)
        return gradient
    
    # Blend images to produce bleedthrough effect
    def blend(self, img, img_bleed, alpha):
        img_PIL = Image.fromarray(img)
        img_bleed_PIL = Image.fromarray(img_bleed)
        img_PIL = img_PIL.convert("RGBA")
        img_bleed_PIL = img_bleed_PIL.convert("RGBA")
        img_blended= Image.blend(img_PIL, img_bleed_PIL, alpha=alpha)
        return np.array(img_blended)  
    
    # Offset image so that bleedthrough effect is visible and not stacked with input image
    def generate_offset(self, img_bleed, offsets):
        x_offset = offsets[0]
        y_offset = offsets[1]
        if (x_offset==0) and (y_offset==0):
            return (img_bleed)
        elif (x_offset==0):
            img_bleed[y_offset:,:] = img_bleed[:-y_offset,:]
        elif (y_offset==0):
            img_bleed[:,x_offset:] = img_bleed[:,:-x_offset]
        else:
            img_bleed[y_offset:, x_offset:] = img_bleed[:-y_offset, :-x_offset]
        return img_bleed
    
    # Preprocess and create bleeding ink effect
    def generate_bleeding_ink(self, img,intensity_range, color_range, ksize, sigmaX):
        intensity = random.uniform(intensity_range[0], intensity_range[1])
        add_noise_fn = (
            lambda x, y: random.randint(color_range[0], color_range[1])
            if (y == 255 and random.random() < intensity)
            else x
        )
        add_noise = np.vectorize(add_noise_fn)
        sobel = self.sobel(img)
        img_noise = add_noise(img, self.add_sp_noise(sobel))
        img_bleed = cv2.GaussianBlur(img_noise, ksize=ksize, sigmaX=sigmaX)   
        return img_bleed

    # Applies the Augmentation to input data.
    def __call__(self, data, force=False):
        if force or self.should_run():
            img = data["ink"][-1].result.copy()

            img_flip = cv2.flip(img, 1)
            img_bleed = self.generate_bleeding_ink(img_flip, self.intensity_range, self.color_range, self.ksize, self.sigmaX)
            img_bleed_offset = self.generate_offset(img_bleed, self.offsets)
            img_bleedthrough = self.blend(img, img_bleed_offset,self.alpha)

            data["ink"].append(AugmentationResult(self, img_bleedthrough))
