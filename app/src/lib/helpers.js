import { IMAGE_EXTENSIONS } from './mime_types';

const flipObject = (obj) =>
  Object.keys(obj).reduce((flipped, key) => {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      flipped[obj[key]] = key;
    }
    return flipped;
  }, {});

const capitalizeFirstLetter = (string) =>
  string ? string.charAt(0).toUpperCase() + string.slice(1) : string;

const isImageFile = (fileExtension) => IMAGE_EXTENSIONS.includes(fileExtension.toLowerCase());

const helpers = {
  flipObject,
  capitalizeFirstLetter,
  isImageFile,
};

export default helpers;
