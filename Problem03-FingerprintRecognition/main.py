import math
import numpy as np
from matplotlib import pyplot as plt
import cv2
import copy
from scipy import ndimage
from scipy.spatial import distance
from scipy import signal
from skimage.morphology import skeletonize
from rindex28_loader import Rindex28Loader
from skimage import img_as_ubyte


# cv2.imshow('', np.concatenate((sobelX, sobelY), axis=1))
# cv2.waitKey(0)


ERROR_LIM = 0.16


def image_enhancement(image):
    mean = np.mean(image)
    std = np.std(image)
    image_enhanced = 150 + 95 * ((image - mean) / float(std))
    image_enhanced[image_enhanced > 255] = 255
    image_enhanced[image_enhanced < 0] = 0
    return np.array(image_enhanced)


def orientation_computation(image):
    sobelX = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=3)
    sobelY = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=3)
    orientations = np.array([])
    averages_x = np.array([])
    averages_y = np.array([])
    for i in xrange(30):
        tmpX = sobelX[i * 10:(i + 1) * 10]
        tmpY = sobelY[i * 10:(i + 1) * 10]
        for j in xrange(30):
            Gx = tmpX[:, j * 10:(j + 1) * 10]
            Gy = tmpY[:, j * 10:(j + 1) * 10]
            average_x = np.sum(np.square(Gx) - np.square(Gy)) / float(100)
            average_y = np.sum(2 * Gx * Gy) / float(100)
            angle = math.atan2(average_y, average_x)/float(2)
            averages_x = np.append(averages_x, average_x)
            averages_y = np.append(averages_y, average_y)
            orientations = np.append(orientations, angle)
    orientations = np.reshape(orientations, (30, 30)) * -1
    averages_x = np.reshape(averages_x, (30, 30))
    averages_y = np.reshape(averages_y, (30, 30))
    return orientations, averages_x, averages_y


def show_orientation_lines(image_org, orientations):
    image = copy.deepcopy(image_org)
    lin_block = 0
    for lin in xrange(5, 300, 10):
        col_block = 0
        for col in xrange(5, 300, 10):
            angle = orientations[lin_block][col_block]
            n = np.tan(angle)
            if(np.abs(n) > 1):
                # varia y + 4 e y - 4
                # calcula x = ((y - y0)/n) + x0
                s_point = (col - 4, int((col - 4 - col)/n + lin))
                f_point = (col + 4, int((col + 4 - col)/n + lin))
            else:
                # varia x + 4 e x - 4
                # calcula y = n(x-x0) + y0
                s_point = (int(n*(lin - 4 - lin) + col), lin - 4)
                f_point = (int(n*(lin + 4 - lin) + col), lin + 4)
            cv2.line(image, s_point, f_point, (0, 0, 0))
            col_block += 1
        lin_block += 1
    plt.imshow(image, cmap='Greys_r')
    plt.show()


def show_interesting_blocks(image_original, interesting_blocks):
    image = copy.deepcopy(image_original)
    lin_block = 0
    for lin in xrange(5, 300, 10):
        col_block = 0
        for col in xrange(5, 300, 10):
            if interesting_blocks[lin_block][col_block]:
                cv2.circle(image, (col, lin), 2, (0, 0, 0), -1)
            col_block += 1
        lin_block += 1
    plt.imshow(image, cmap='Greys_r')
    plt.show()


def regions_of_interest(image):
    interesting_blocks = np.zeros((30, 30), dtype=np.bool)
    max_distance = float(150 * np.sqrt(2))
    for i in xrange(30):
        tmpImg = image[i * 10:(i + 1) * 10]
        for j in xrange(30):
            block = tmpImg[:, j * 10:(j + 1) * 10]
            curret_distance = np.linalg.norm([150 - i, 150 - j])
            distance_ratio = (max_distance - curret_distance)/max_distance
            mean = np.mean(block)/float(255)
            standard_deviation = np.std(block)/float(255)
            v = 0.5 * (1-mean) + 0.5 * standard_deviation + distance_ratio
            if v > 0.35:
                interesting_blocks[i][j] = True
    return interesting_blocks


def smooth_block(block):
    filter = np.array([[1, 1, 1], [1, 2, 1], [1, 1, 1]])
    return np.sum(np.multiply(block, filter))


def smooth_orientations(averages_x, averages_y, interesting_blocks):
    orientations = np.zeros((30, 30))
    for lin in xrange(1, 29):
        for col in xrange(1, 29):
            if interesting_blocks[lin, col]:
                a = smooth_block(averages_x[lin - 1:lin + 2, col - 1:col + 2])
                b = smooth_block(averages_y[lin - 1:lin + 2, col - 1:col + 2])
                orientations[lin][col] = math.atan2(b, a)/float(2)
    return orientations * -1


def delta(value):
    if abs(value) < np.pi/float(2):
        return value
    if value <= -np.pi/float(2):
        return np.pi + value
    return np.pi - value


def poincare(block):
    block = block.reshape((3, 3))
    sum1 = delta(block[0][0] - block[1][0]) + delta(block[1][0] - block[2][0])
    sum1 += delta(block[2][0] - block[2][1])
    sum2 = delta(block[2][1] - block[2][2]) + delta(block[2][2] - block[1][2])
    sum2 += delta(block[1][2] - block[0][2])
    sum3 = delta(block[0][2] - block[0][1]) + delta(block[0][1] - block[0][0])
    return (sum1 + sum2 + sum3)/float(np.pi*2)


def singular_points_detection(orientations, interesting_blocks):
    cores = []
    deltas = []
    poincare_matrix = ndimage.filters.generic_filter(
        orientations, poincare, (3, 3)
    )
    lin_max, col_max = poincare_matrix.shape
    min_distance = 2 * math.sqrt(2)
    for lin in xrange(1, lin_max):
        for col in xrange(1, col_max):
            sum = poincare_matrix[lin][col]
            point_block = (lin, col)
            point_original = ((lin * 10) + 5, (col * 10) + 5)
            if not block_all_true(lin, col, interesting_blocks):
                continue
            if is_delta(sum):
                if not deltas:
                    deltas.append(point_original)
                else:
                    last_delta = deltas[-1]
                    last_delta = ((last_delta[0] - 5)/10, (last_delta[1] - 5)/10)
                    if eucli_distance(point_block, last_delta) > min_distance:
                        deltas.append(point_original)
            if is_core(sum):
                if not cores:
                    cores.append(point_original)
                else:
                    last_core = cores[-1]
                    last_core = ((last_core[0] - 5)/10, (last_core[1] - 5)/10)
                    if eucli_distance(point_block, last_core) > min_distance:
                        cores.append(point_original)
    return cores, deltas


def block_all_true(lin, col, matrix):
    block = matrix[lin - 1:lin + 2, col - 1:col + 2]
    return np.all(block)


def eucli_distance(point1, point2):
    return distance.euclidean(point1, point2)


def is_delta(value):
    error_lim = ERROR_LIM
    return (0.5 - error_lim <= value <= 0.5 + error_lim)


def is_core(value):
    error_lim = ERROR_LIM
    return (-0.5 - error_lim <= value <= -0.5 + error_lim)


def show_singular_points(image_original, cores, deltas, title=''):
    image = copy.deepcopy(image_original)
    for coord in cores:
        coord = reverse_tuple(coord)
        cv2.rectangle(image, coord, (coord[0]+4, coord[1]+4), (0, 0, 0))
    for coord in deltas:
        coord = reverse_tuple(coord)
        cv2.circle(image, coord, 4, (0, 0, 0), -1)
    plt.imshow(image, cmap='Greys_r')
    plt.title(title)
    plt.show()


def reverse_tuple(tuple):
    return tuple[::-1]


def classify_deltas(deltas, image):
    left_deltas = 0
    right_deltas = 0
    center_deltas = 0
    width = 300
    for delta in deltas:
        if delta[1] < width/3.0:
            left_deltas += 1
        elif delta[1] < 2 * width/3.0:
            center_deltas += 1
        else:
            right_deltas += 1
    return left_deltas, center_deltas, right_deltas


def classify(cores, deltas, image):
    cores = len(cores)
    left_deltas, center_deltas, right_deltas = classify_deltas(deltas, image)
    total_deltas = left_deltas + center_deltas + right_deltas
    if cores == 1 and right_deltas == 1:
        return 'left loop'
    if cores == 1 and left_deltas == 1:
        return 'right loop'
    if cores == 1 and 0 <= center_deltas <= 1:
        return 'arch'
    if cores == 2 and 0 <= total_deltas <= 2:
        return 'whorl'
    return 'others'


def find_percent_in_hist(hist, value):
    n_pixels = np.sum(hist)
    current = 0
    for i in xrange(len(hist)):
        current += hist[i]
        if current/float(n_pixels) >= value:
            break
    return i


def image_binarization(image_original):
    img = copy.deepcopy(image_original)
    width, heigth = img.shape
    histogram = cv2.calcHist([img.astype(np.float32)], [0], None, [256], [0, 256])
    p25 = find_percent_in_hist(histogram, 0.25)
    p50 = find_percent_in_hist(histogram, 0.5)

    mean_blocks = []
    for i in xrange(0, width, 10):
        for j in xrange(0, heigth, 10):
            mean_blocks.append(
                np.mean(image_original[i:i + 10, j:j + 10])
            )
    mean_blocks = np.array(mean_blocks).reshape(width/10, heigth/10)

    for i in xrange(width):
        for j in xrange(heigth):
            if image_original[i][j] < p25:
                img[i][j] = 0
            elif image_original[i][j] > p50:
                img[i][j] = 255
            else:
                block = image_original[i - 1:i + 2, j - 1:j + 2]
                sum_neighbors = (np.mean(block) - image_original[i][j])/8
                if sum_neighbors >= mean_blocks[i/10][j/10]:
                    img[i][j] = 255
                else:
                    img[i][j] = 0
    return np.array(img)


def smooth_filter_5(block):
    center_index = len(block)/2
    center = block[center_index]
    neighbors = np.delete(block, center_index)
    n_of_whites = len(neighbors[np.where(neighbors == 255)])
    n_of_blacks = len(neighbors[np.where(neighbors == 0)])
    if n_of_whites >= 18:
        return 255
    elif n_of_blacks >= 18:
        return 0
    else:
        return center


def smooth_filter_3(block):
    center_index = len(block)/2
    center = block[center_index]
    neighbors = np.delete(block, center_index)
    n_of_whites = len(neighbors[np.where(neighbors == 255)])
    n_of_blacks = len(neighbors[np.where(neighbors == 0)])
    if n_of_whites >= 5:
        return 255
    elif n_of_blacks >= 5:
        return 0
    else:
        return center


def smooth_image(original_image):
    image_5 = ndimage.filters.generic_filter(
        original_image, smooth_filter_5, (5, 5)
    )
    image_3 = ndimage.filters.generic_filter(image_5, smooth_filter_3, (3, 3))
    return image_3


def image_thinning(img):
    return np.invert(skeletonize(img == np.zeros(img.shape)))


def define_minutiaes(block, interesting_block):
    block = block.flatten()
    interesting_block = interesting_block.flatten()
    center_index = len(block)/2
    center = block[center_index]
    neighbors = np.delete(block, center_index)
    if center != 0:
        return 0
    if np.any(interesting_block == False):
        return 0
    n_of_blacks = len(neighbors[np.where(neighbors == 0)])
    if n_of_blacks == 0:
        return 1
    elif n_of_blacks == 1:
        return 2
    elif n_of_blacks == 2:
        return 3
    elif n_of_blacks == 3:
        return 4
    else:
        return 5


def minutiaes_detection(image, interesting_blocks):
    width, heigth = image.shape
    minutiaes = np.zeros((width, heigth))
    for i in xrange(1, width - 1):
        block_tmp = image[i - 1: i + 2]
        interesting_block_tmp = interesting_blocks[i - 1: i + 2]
        for j in xrange(1, heigth - 1):
            block = block_tmp[:, j - 1: j + 2]
            interesting_block = interesting_block_tmp[:, j - 1: j + 2]
            minutiaes[i][j] = define_minutiaes(block, interesting_block)
    return minutiaes


rindex28 = Rindex28Loader('./databases/rindex28')
for image in rindex28.images:
    image_enhanced = image_enhancement(image)
    blurred_image = signal.medfilt(image_enhanced, 5)

    # plt.imshow(blurred_image, cmap='Greys_r')
    # plt.show()

    orientations, averages_x, averages_y = orientation_computation(
        blurred_image
    )
    # show_orientation_lines(image, orientations)

    interesting_blocks = regions_of_interest(image_enhanced)
    # show_interesting_blocks(image, interesting_blocks)

    smoothed_orientations = smooth_orientations(
        averages_x, averages_y, interesting_blocks
    )
    # show_orientation_lines(image, smoothed_orientations)

    cores, deltas = singular_points_detection(
        smoothed_orientations, interesting_blocks
    )
    classification = classify(cores, deltas, interesting_blocks)

    # show_singular_points(image, cores, deltas, title=classification)

    binarized_image = image_binarization(image_enhanced)

    # plt.imshow(binarized_image, cmap='Greys_r')
    # plt.show()

    smoothed_image = smooth_image(binarized_image)

    # plt.imshow(smoothed_image, cmap='Greys_r')
    # plt.show()

    thin_image = image_thinning(smoothed_image)

    # plt.imshow(thin_image, cmap='Greys_r')
    # plt.show()

    minutiaes = minutiaes_detection(thin_image, interesting_blocks)


    tmp_image = copy.deepcopy(thin_image).astype(np.float)
    tmp_image[tmp_image == 1] = 255
    for i in xrange(300):
        for j in xrange(300):
            if minutiaes[i][j] != 0:
                cv2.circle(tmp_image, (j, i), 2, (0, 0, 0), -1)
    plt.imshow(tmp_image, cmap='Greys_r')
    plt.show()
