import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt


class InputToCx(tf.keras.layers.Layer):
    def __init__(self, output_dim):
        super(InputToCx, self).__init__()
        self.output_dim = output_dim

    def call(self, inputs, **kwargs):
        ini_phase = 0.0
        delta = 0.0
        rcp_x_real = inputs * tf.cos(ini_phase) / tf.sqrt(2.0)
        rcp_x_imag = inputs * tf.sin(ini_phase) / tf.sqrt(2.0)
        rcp_y_real = inputs * -tf.sin(ini_phase) / tf.sqrt(2.0)
        rcp_y_imag = inputs * tf.cos(ini_phase) / tf.sqrt(2.0)

        lcp_x_real = inputs * tf.cos(ini_phase - delta) / tf.sqrt(2.0)
        lcp_x_imag = inputs * tf.sin(ini_phase - delta) / tf.sqrt(2.0)
        lcp_y_real = inputs * tf.sin(ini_phase - delta) / tf.sqrt(2.0)
        lcp_y_imag = inputs * -tf.cos(ini_phase - delta) / tf.sqrt(2.0)

        rcp = tf.stack([rcp_x_real, rcp_x_imag, rcp_y_real, rcp_y_imag], axis=1) / tf.sqrt(2.0)
        lcp = tf.stack([lcp_x_real, lcp_x_imag, lcp_y_real, lcp_y_imag], axis=1) / tf.sqrt(2.0)

        return tf.stack([rcp, lcp], axis=1)


class CxMO(tf.keras.layers.Layer):
    def __init__(self, output_dim):
        super(CxMO, self).__init__()
        self.output_dim = output_dim

    def build(self, input_dim):
        self.phi = self.add_weight("phi",
                                   shape=[int(input_dim[-2]),
                                          int(input_dim[-1])])

        super(CxMO, self).build(input_dim)

    def call(self, x):
        x_rcp = x[:, 0, 0:2, :, :]
        y_rcp = x[:, 0, 2:4, :, :]
        x_lcp = x[:, 1, 0:2, :, :]
        y_lcp = x[:, 1, 2:4, :, :]

        # x_rcp[0,:,:] : real
        # x_rcp[1,:,:] : imag

        mo_real = tf.cos(self.phi)
        mo_imag = tf.sin(self.phi)

        rcp_x_real = x_rcp[:, 0, :, :] * mo_real - x_rcp[:, 1, :, :] * mo_imag
        rcp_x_imag = x_rcp[:, 0, :, :] * mo_imag + x_rcp[:, 1, :, :] * mo_real

        rcp_y_real = y_rcp[:, 0, :, :] * mo_real - y_rcp[:, 1, :, :] * mo_imag
        rcp_y_imag = y_rcp[:, 0, :, :] * mo_imag + y_rcp[:, 1, :, :] * mo_real

        lcp_x_real = x_lcp[:, 0, :, :] * mo_real - x_lcp[:, 1, :, :] * -mo_imag
        lcp_x_imag = x_lcp[:, 0, :, :] * -mo_imag + x_lcp[:, 1, :, :] * mo_real

        lcp_y_real = y_lcp[:, 0, :, :] * mo_real - y_lcp[:, 1, :, :] * -mo_imag
        lcp_y_imag = y_lcp[:, 0, :, :] * -mo_imag + y_lcp[:, 1, :, :] * mo_real

        rcp = tf.stack([rcp_x_real, rcp_x_imag, rcp_y_real, rcp_y_imag], axis=1)
        lcp = tf.stack([lcp_x_real, lcp_x_imag, lcp_y_real, lcp_y_imag], axis=1)

        return tf.stack([rcp, lcp], axis=1)


class FreeSpacePropagation(tf.keras.layers.Layer):
    def __init__(self, output_dim, k, z, input_pitch=1e-6, output_pitch=1e-6, normalization=None):
        super(FreeSpacePropagation, self).__init__()
        self.output_dim = output_dim
        self.input_pitch = input_pitch
        self.output_pitch = output_pitch
        self.z = z
        self.k = k
        self.normalization = normalization

    def build(self, input_shape):
        x1 = np.arange(0, input_shape[-1], 1)
        y1 = np.arange(0, input_shape[-2], 1)
        xx1, yy1 = np.meshgrid(x1, y1)
        xx1 = xx1.reshape(-1, 1) - input_shape[-1] / 2
        yy1 = yy1.reshape(-1, 1) - input_shape[-2] / 2

        x2 = np.arange(0, self.output_dim[1], 1)
        y2 = np.arange(0, self.output_dim[0], 1)
        xx2, yy2 = np.meshgrid(x2, y2)
        xx2 = xx2.reshape(1, -1) - self.output_dim[1] / 2
        yy2 = yy2.reshape(1, -1) - self.output_dim[0] / 2

        dx = (self.output_pitch * xx2 - self.input_pitch * xx1)
        dy = (self.output_pitch * yy2 - self.input_pitch * yy1)
        r = np.sqrt(dx ** 2 + dy ** 2 + self.z ** 2)
        self.r = r
        w = 1.0 / (2.0 * np.pi) * self.z / r * (1.0 / r - 1.0j * self.k) * np.exp(1.0j * self.k * r)

        self.w_real = tf.constant(w.real.astype('float32'))
        self.w_imag = tf.constant(w.imag.astype('float32'))

        super(FreeSpacePropagation, self).build(input_shape)

    def call(self, x, **kwargs):
        x_rcp = tf.keras.layers.Lambda(lambda x: x[:, 0, 0:2, :, :], output_shape=(self.output_dim,))(x)
        y_rcp = tf.keras.layers.Lambda(lambda x: x[:, 0, 2:4, :, :], output_shape=(self.output_dim,))(x)
        x_lcp = tf.keras.layers.Lambda(lambda x: x[:, 1, 0:2, :, :], output_shape=(self.output_dim,))(x)
        y_lcp = tf.keras.layers.Lambda(lambda x: x[:, 1, 2:4, :, :], output_shape=(self.output_dim,))(x)

        x_rcp = tf.reshape(x_rcp, (-1, 2, x.shape[-1] * x.shape[-2]))
        y_rcp = tf.reshape(y_rcp, (-1, 2, x.shape[-1] * x.shape[-2]))
        x_lcp = tf.reshape(x_lcp, (-1, 2, x.shape[-1] * x.shape[-2]))
        y_lcp = tf.reshape(y_lcp, (-1, 2, x.shape[-1] * x.shape[-2]))

        rcp_x_real = tf.matmul(x_rcp[:, 0, :], self.w_real) - tf.matmul(x_rcp[:, 1, :], self.w_imag)
        rcp_x_imag = tf.matmul(x_rcp[:, 0, :], self.w_imag) + tf.matmul(x_rcp[:, 1, :], self.w_real)
        rcp_x_real = tf.reshape(rcp_x_real, (-1, self.output_dim[0], self.output_dim[1]))
        rcp_x_imag = tf.reshape(rcp_x_imag, (-1, self.output_dim[0], self.output_dim[1]))

        rcp_y_real = tf.matmul(y_rcp[:, 0, :], self.w_real) - tf.matmul(y_rcp[:, 1, :], self.w_imag)
        rcp_y_imag = tf.matmul(y_rcp[:, 0, :], self.w_imag) + tf.matmul(y_rcp[:, 1, :], self.w_real)
        rcp_y_real = tf.reshape(rcp_y_real, (-1, self.output_dim[0], self.output_dim[1]))
        rcp_y_imag = tf.reshape(rcp_y_imag, (-1, self.output_dim[0], self.output_dim[1]))

        lcp_x_real = tf.matmul(x_lcp[:, 0, :], self.w_real) - tf.matmul(x_lcp[:, 1, :], self.w_imag)
        lcp_x_imag = tf.matmul(x_lcp[:, 0, :], self.w_imag) + tf.matmul(x_lcp[:, 1, :], self.w_real)
        lcp_x_real = tf.reshape(lcp_x_real, (-1, self.output_dim[0], self.output_dim[1]))
        lcp_x_imag = tf.reshape(lcp_x_imag, (-1, self.output_dim[0], self.output_dim[1]))

        lcp_y_real = tf.matmul(y_lcp[:, 0, :], self.w_real) - tf.matmul(y_lcp[:, 1, :], self.w_imag)
        lcp_y_imag = tf.matmul(y_lcp[:, 0, :], self.w_imag) + tf.matmul(y_lcp[:, 1, :], self.w_real)
        lcp_y_real = tf.reshape(lcp_y_real, (-1, self.output_dim[0], self.output_dim[1]))
        lcp_y_imag = tf.reshape(lcp_y_imag, (-1, self.output_dim[0], self.output_dim[1]))

        rcp = tf.stack([rcp_x_real, rcp_x_imag, rcp_y_real, rcp_y_imag], axis=1)
        lcp = tf.stack([lcp_x_real, lcp_x_imag, lcp_y_real, lcp_y_imag], axis=1)

        cmpx = tf.stack([rcp, lcp], axis=1)

        if self.normalization == 'max':
            absmax = tf.reduce_max(tf.abs(cmpx))
            cmpx = cmpx / absmax

        return cmpx


class CxD2NNIntensity(tf.keras.layers.Layer):
    def __init__(self, output_dim, normalization='max', **kwargs):
        super(CxD2NNIntensity, self).__init__(**kwargs)
        self.output_dim = output_dim
        self.normalization = normalization

    def call(self, x, **kwargs):
        x_rcp = tf.keras.layers.Lambda(lambda x: x[:, 0, 0:2, :, :], output_shape=(self.output_dim,))(x)
        y_rcp = tf.keras.layers.Lambda(lambda x: x[:, 0, 2:4, :, :], output_shape=(self.output_dim,))(x)
        x_lcp = tf.keras.layers.Lambda(lambda x: x[:, 1, 0:2, :, :], output_shape=(self.output_dim,))(x)
        y_lcp = tf.keras.layers.Lambda(lambda x: x[:, 1, 2:4, :, :], output_shape=(self.output_dim,))(x)

        tot_x = x_rcp + x_lcp
        tot_y = y_rcp + y_lcp

        intensity = tot_x[:, 0, :, :] ** 2 + tot_x[:, 1, :, :] ** 2 + tot_y[:, 0, :, :] ** 2 + tot_y[:, 1, :, :] ** 2
        if self.normalization == 'min_max':
            max = tf.reduce_max(intensity)
            min = tf.reduce_min(intensity)
            intensity = (intensity - min) / (max - min)
        elif self.normalization == 'max':
            max = tf.reduce_max(intensity)
            intensity = intensity / max

        return intensity


class CxD2NNMNISTDetector(tf.keras.layers.Layer):
    def __init__(self, output_dim, activation=None, **kwargs):
        super(CxD2NNMNISTDetector, self).__init__(**kwargs)
        self.output_dim = output_dim
        self.activation = activation

    def build(self, input_shape):
        self.input_dim = input_shape
        self.width = min(int(tf.floor(self.input_dim[2] / 9.0)), int(tf.floor(self.input_dim[1] / 7.0)))
        self.height = min(int(tf.floor(self.input_dim[2] / 9.0)), int(tf.floor(self.input_dim[1] / 7.0)))
        super(CxD2NNMNISTDetector, self).build(input_shape)

    def plot_area(self, input_shape, same_color=False):
        width = min(int(np.floor(input_shape[1] / 9.0)), int(np.floor(input_shape[0] / 7.0)))
        height = min(int(np.floor(input_shape[1] / 9.0)), int(np.floor(input_shape[0] / 7.0)))
        x = np.zeros(input_shape)
        if same_color:
            x[2 * height:3 * height, width:2 * width] = 1
            x[2 * height:3 * height, 4 * width:5 * width] = 1
            x[2 * height:3 * height, 7 * width:8 * width] = 1
            x[4 * height:5 * height, 1 * width:2 * width] = 1
            x[4 * height:5 * height, 3 * width:4 * width] = 1
            x[4 * height:5 * height, 5 * width:6 * width] = 1
            x[4 * height:5 * height, 7 * width:8 * width] = 1
            x[6 * height:7 * height, width:2 * width] = 1
            x[6 * height:7 * height, 4 * width:5 * width] = 1
            x[6 * height:7 * height, 7 * width:8 * width] = 1
        else:
            x[2 * height:3 * height, width:2 * width] = 1
            x[2 * height:3 * height, 4 * width:5 * width] = 2
            x[2 * height:3 * height, 7 * width:8 * width] = 3
            x[4 * height:5 * height, 1 * width:2 * width] = 4
            x[4 * height:5 * height, 3 * width:4 * width] = 5
            x[4 * height:5 * height, 5 * width:6 * width] = 6
            x[4 * height:5 * height, 7 * width:8 * width] = 7
            x[6 * height:7 * height, width:2 * width] = 8
            x[6 * height:7 * height, 4 * width:5 * width] = 9
            x[6 * height:7 * height, 7 * width:8 * width] = 10
        plt.imshow(x)

    def call(self, x, **kwargs):
        y0 = tf.keras.layers.Lambda(lambda x: x[:, 2 * self.height:3 * self.height, self.width:2 * self.width])(x)
        y1 = tf.keras.layers.Lambda(lambda x: x[:, 2 * self.height:3 * self.height, 4 * self.width:5 * self.width])(x)
        y2 = tf.keras.layers.Lambda(lambda x: x[:, 2 * self.height:3 * self.height, 7 * self.width:8 * self.width])(x)
        y3 = tf.keras.layers.Lambda(lambda x: x[:, 4 * self.height:5 * self.height, self.width:2 * self.width])(x)
        y4 = tf.keras.layers.Lambda(lambda x: x[:, 4 * self.height:5 * self.height, 3 * self.width:4 * self.width])(x)
        y5 = tf.keras.layers.Lambda(lambda x: x[:, 4 * self.height:5 * self.height, 5 * self.width:6 * self.width])(x)
        y6 = tf.keras.layers.Lambda(lambda x: x[:, 4 * self.height:5 * self.height, 7 * self.width:8 * self.width])(x)
        y7 = tf.keras.layers.Lambda(lambda x: x[:, 6 * self.height:7 * self.height, self.width:2 * self.width])(x)
        y8 = tf.keras.layers.Lambda(lambda x: x[:, 6 * self.height:7 * self.height, 4 * self.width:5 * self.width])(x)
        y9 = tf.keras.layers.Lambda(lambda x: x[:, 6 * self.height:7 * self.height, 7 * self.width:8 * self.width])(x)
        y0 = tf.reduce_sum(y0, axis=[1])
        y0 = tf.reduce_sum(y0, axis=[1], keepdims=True)
        y1 = tf.reduce_sum(y1, axis=[1])
        y1 = tf.reduce_sum(y1, axis=[1], keepdims=True)
        y2 = tf.reduce_sum(y2, axis=[1])
        y2 = tf.reduce_sum(y2, axis=[1], keepdims=True)
        y3 = tf.reduce_sum(y3, axis=[1])
        y3 = tf.reduce_sum(y3, axis=[1], keepdims=True)
        y4 = tf.reduce_sum(y4, axis=[1])
        y4 = tf.reduce_sum(y4, axis=[1], keepdims=True)
        y5 = tf.reduce_sum(y5, axis=[1])
        y5 = tf.reduce_sum(y5, axis=[1], keepdims=True)
        y6 = tf.reduce_sum(y6, axis=[1])
        y6 = tf.reduce_sum(y6, axis=[1], keepdims=True)
        y7 = tf.reduce_sum(y7, axis=[1])
        y7 = tf.reduce_sum(y7, axis=[1], keepdims=True)
        y8 = tf.reduce_sum(y8, axis=[1])
        y8 = tf.reduce_sum(y8, axis=[1], keepdims=True)
        y9 = tf.reduce_sum(y9, axis=[1])
        y9 = tf.reduce_sum(y9, axis=[1], keepdims=True)

        y = tf.keras.layers.concatenate([y0, y1, y2, y3, y4, y5, y6, y7, y8, y9])

        if self.activation == 'softmax':
            y = tf.nn.softmax(y)
        return y


class Detector(tf.keras.layers.Layer):
    def __init__(self, output_dim, activation=None, **kwargs):
        super(Detector, self).__init__(**kwargs)
        self.output_dim = output_dim
        self.activation = activation

    def build(self, input_shape):
        self.input_dim = input_shape
        width = min(int(tf.floor(self.input_dim[2] / 9.0)), int(tf.floor(self.input_dim[1] / 7.0)))
        height = min(int(tf.floor(self.input_dim[2] / 9.0)), int(tf.floor(self.input_dim[1] / 7.0)))

        w0 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w0[2 * height:3 * height, width:2 * width] = 1.0
        w0 = tf.constant(w0.reshape(-1))

        w1 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w1[2 * height:3 * height, 4 * width:5 * width] = 1.0
        w1 = tf.constant(w1.reshape(-1))

        w2 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w2[2 * height:3 * height, 7 * width:8 * width] = 1.0
        w2 = tf.constant(w2.reshape(-1))

        w3 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w3[4 * height:5 * height, 1 * width:2 * width] = 1.0
        w3 = tf.constant(w3.reshape(-1))

        w4 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w4[4 * height:5 * height, 3 * width:4 * width] = 1.0
        w4 = tf.constant(w4.reshape(-1))

        w5 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w5[4 * height:5 * height, 5 * width:6 * width] = 1.0
        w5 = tf.constant(w5.reshape(-1))

        w6 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w6[4 * height:5 * height, 7 * width:8 * width] = 1.0
        w6 = tf.constant(w6.reshape(-1))

        w7 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w7[6 * height:7 * height, width:2 * width] = 1.0
        w7 = tf.constant(w7.reshape(-1))

        w8 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w8[6 * height:7 * height, 4 * width:5 * width] = 1.0
        w8 = tf.constant(w8.reshape(-1))

        w9 = np.zeros((self.input_dim[-2], self.input_dim[-1]), dtype='float32')
        w9[6 * height:7 * height, 7 * width:8 * width] = 1.0
        w9 = tf.constant(w9.reshape(-1))

        self.filter = tf.stack([w0, w1, w2, w3, w4, w5, w6, w7, w8, w9], axis=1)

    def call(self, x, **kwargs):
        # y0 = tf.reduce_sum(x * self.w0)
        # y0 = tf.tensordot(x, self.w0, axes=[[1, 2], [0, 1]])
        # y1 = tf.tensordot(x, self.w1, axes=[[1, 2], [0, 1]])
        # y2 = tf.tensordot(x, self.w2, axes=[[1, 2], [0, 1]])
        # y3 = tf.tensordot(x, self.w3, axes=[[1, 2], [0, 1]])
        # y4 = tf.tensordot(x, self.w4, axes=[[1, 2], [0, 1]])
        # y5 = tf.tensordot(x, self.w5, axes=[[1, 2], [0, 1]])
        # y6 = tf.tensordot(x, self.w6, axes=[[1, 2], [0, 1]])
        # y7 = tf.tensordot(x, self.w7, axes=[[1, 2], [0, 1]])
        # y8 = tf.tensordot(x, self.w8, axes=[[1, 2], [0, 1]])
        # y9 = tf.tensordot(x, self.w9, axes=[[1, 2], [0, 1]])

        x = tf.reshape(x, (-1, self.input_dim[-2] * self.input_dim[-1]))
        y = tf.tensordot(x, self.filter, axes=[1, 0])

        if self.activation == 'softmax':
            y = tf.nn.softmax(y)
        return y


class ImageResize(tf.keras.layers.Layer):
    def __init__(self, output_dim):
        super(ImageResize, self).__init__()
        self.output_dim = output_dim

    def call(self, x):
        x_expnad = tf.image.resize(tf.expand_dims(x, -1), self.output_dim)
        x_expnad = tf.keras.layers.Lambda(lambda x: x[:, :, :, 0])(x_expnad)
        return x_expnad


class CxD2NNStokes(tf.keras.layers.Layer):
    def __init__(self, output_dim):
        super(InputToCx, self).__init__()
        self.output_dim = output_dim

    def call(self, x, **kwargs):
        rcp_x = x[0, 0, 0:2, :, :]
        rcp_y = x[0, 0, 2:4, :, :]
        lcp_x = x[0, 1, 0:2, :, :]
        lcp_y = x[0, 1, 2:4, :, :]

        E0 = rcp_x + lcp_x
        I0 = E0[0, :, :] ** 2 + E0[1, :, :] ** 2
        E90 = rcp_y + lcp_y
        I90 = E90[0, :, :] ** 2 + E90[1, :, :] ** 2
        E45_x = (rcp_x + rcp_y + lcp_x + lcp_y) / 2
        E45_y = (rcp_x + rcp_y + lcp_x + lcp_y) / 2
        I45 = E45_x[0, :, :] ** 2 + E45_x[1, :, :] ** 2 + E45_y[0, :, :] ** 2 + E45_y[1, :, :] ** 2
        E135_x = (rcp_x - rcp_y + lcp_x - lcp_y) / 2
        E135_y = (-rcp_x + rcp_y - lcp_x + lcp_y) / 2
        I135 = E135_x[0, :, :] ** 2 + E135_x[1, :, :] ** 2 + E135_y[0, :, :] ** 2 + E135_y[1, :, :] ** 2
        E_tot_x = rcp_x + lcp_x
        E_tot_y = rcp_y + lcp_y

        S0 = (I0 + I90 + I45 + I135) / 2
        S1 = I0 - I90
        S2 = I45 - I135

        return tf.stack([S0, S1, S2], axis=1)


if __name__ == '__main__':
    pass
