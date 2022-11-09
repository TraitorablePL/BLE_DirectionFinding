import math
import cmath
import json
import numpy as np

class Localization():

    def __init__(self):
        self.vel_air = 299702547 # m/s
        self.freq = 2460000000 # Hz might depend on currently used channel
        self.wave_len = self.vel_air/self.freq
        self.d = 0.05 # m, distance between antennas
        pass

    def to_plus_minus_pi(self, angle):
        while angle >= 180:
            angle -= 2 * 180
        while angle < -180:
            angle += 2 * 180
        return angle

    def calc_mean(self, values):
        if len(values) == 0:
            return 0
        else:
            return sum(values)/len(values)

    def calc_angle(self, deg_value, inverted, results):
        output = 0
        try:
            result = math.acos((np.deg2rad(deg_value)*self.wave_len)/(2*math.pi*self.d))
        except ValueError:
            pass
        else:
            if inverted:
                output = abs(self.to_plus_minus_pi(np.rad2deg(result)+180))
            else:
                output = abs(self.to_plus_minus_pi(np.rad2deg(result)))
        results.append(output)

    ## Basic algorithm for localization
    def locate_basic(self, data):
        IQ = []
        # Iterate through each IQ sample to normalize it 
        for elem in data["IQ"]:
            I = elem[0]/128 if elem[0] < 0 else elem[0]/127
            Q = elem[1]/128 if elem[1] < 0 else elem[1]/127
            IQ.append(complex(I,Q))

        refPeriodDiff = []
        sampPeriodDiff = []
        refMeanDiff = 0

        # Iterate through each sample (82) in one connection event 
        for i in range(len(IQ)-1):
            # Phase calculation from IQ samples
            phaseCurrent = np.rad2deg(np.arctan2(IQ[i].imag, IQ[i].real))
            phaseNext = np.rad2deg(np.arctan2(IQ[i + 1].imag, IQ[i + 1].real))

            if (i < 7):
                refPeriodDiff.append(abs(self.to_plus_minus_pi(phaseNext - phaseCurrent)))
            elif (i == 7):
                refMeanDiff = self.calc_mean(refPeriodDiff)
            else:
                # 2*refMeanDiff as a in ref period sample is taken twice as fast as in sampling period, 
                # so it needs to be doubled
                sampPeriodDiff.append(self.to_plus_minus_pi((phaseNext - phaseCurrent) - 2*refMeanDiff))

        azimuth = []
        elevation = []
        inverted = False
        horizontal = True

        # Calculate direction angles
        for i in range(len(sampPeriodDiff)-1):
            # Skip corner differences samples
            if ((i + 1) % 4 == 0):
                if(not horizontal): 
                    # Change to inverted after 2 sections of non inverted data due to opposite scanning direction
                    inverted = not inverted
                # Change orientation after each section 
                horizontal = not horizontal
            else:
                if (horizontal):
                    self.calc_angle(sampPeriodDiff[i], inverted, azimuth)
                else:
                    self.calc_angle(sampPeriodDiff[i], inverted, elevation)

        return (self.calc_mean(azimuth), self.calc_mean(elevation))
      
    ## MUSIC algorithm for localization
    def locate_MUSIC(self):
        pass
