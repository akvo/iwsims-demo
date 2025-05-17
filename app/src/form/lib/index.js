import * as Yup from 'yup';
import { helpers, i18n } from '../../lib';
import { SUBMISSION_TYPES } from '../../lib/constants';

export const intersection = (array1, array2) => {
  const set1 = new Set(array1);
  const result = [];
  // eslint-disable-next-line no-restricted-syntax
  for (const item of array2) {
    if (set1.has(item)) {
      result.push(item);
    }
  }
  return result;
};

const getDependencyAncestors = (questions, current, dependencies) => {
  const ids = dependencies.map((x) => x.id);
  const ancestors = questions.filter((q) => ids.includes(q.id)).filter((q) => q?.dependency);
  if (ancestors.length) {
    // eslint-disable-next-line no-param-reassign
    current = [current, ...ancestors.map((x) => x.dependency)].flatMap((x) => x);
    ancestors.forEach((a) => {
      if (a?.dependency) {
        // eslint-disable-next-line no-param-reassign
        current = getDependencyAncestors(questions, current, a.dependency);
      }
    });
  }
  return current;
};

export const onFilterDependency = (currentGroup, values, q) => {
  if (q?.dependency) {
    const modifiedDependency = modifyDependency(currentGroup, q, 0);
    const unmatches = modifiedDependency
      .map((x) => validateDependency(x, values?.[x.id]))
      .filter((x) => x === false);
    if (unmatches.length) {
      return false;
    }
  }
  return q;
};

export const transformForm = (
  forms,
  currentValues,
  lang = 'en',
  submissionType = SUBMISSION_TYPES.registration,
) => {
  const nonEnglish = lang !== 'en';
  const currentForm = nonEnglish ? i18n.transform(lang, forms) : forms;
  const questions = currentForm.question_group
    .map((x) => x.question)
    .flatMap((q) => q)
    .map((q) => (nonEnglish ? i18n.transform(lang, q) : q))
    .map((q) => {
      if (q.type === 'option' || q.type === 'multiple_option') {
        const options = q.option.map((o) => (nonEnglish ? i18n.transform(lang, o) : o));
        return {
          ...q,
          option: options.sort((a, b) => a.order - b.order),
        };
      }
      if (q?.tooltip) {
        const transTooltip = nonEnglish ? i18n.transform(lang, q.tooltip) : q.tooltip;
        return {
          ...q,
          tooltip: transTooltip,
        };
      }
      return q;
    });
  const filteredQuestions = questions
    .map((q) => {
      const subTypeName = helpers.flipObject(SUBMISSION_TYPES)?.[submissionType];
      const disabled = q?.disabled ? q.disabled?.submission_type?.includes(subTypeName) : false;
      // handle hidden question
      const hidden = q?.hidden ? q.hidden?.submission_type?.includes(subTypeName) : false;
      return {
        ...q,
        disabled,
        hidden,
      };
    })
    .filter((q) => !q?.hidden); // remove hidden question from question lists

  const transformed = filteredQuestions.map((x) => {
    let requiredSignTemp = x?.requiredSign || null;
    if (x?.required && !x?.requiredSign) {
      requiredSignTemp = '*';
    }
    if (x?.dependency) {
      return {
        ...x,
        requiredSign: requiredSignTemp,
        dependency: getDependencyAncestors(filteredQuestions, x.dependency, x.dependency),
      };
    }
    return {
      ...x,
      requiredSign: requiredSignTemp,
    };
  });

  return {
    ...forms,
    question_group: forms.question_group
      .sort((a, b) => a.order - b.order)
      .map((qg, qgi) => {
        let repeat = {};
        let repeats = {};
        if (qg?.repeatable) {
          repeat = { repeat: 1 };
          repeats = { repeats: [0] };
        }
        const translatedQg = nonEnglish ? i18n.transform(lang, qg) : qg;
        const transformedQuestions = qg.question
          ?.sort((a, b) => a.order - b.order)
          ?.map((q) => transformed.find((t) => t.id === q.id))
          ?.filter((q) => q)
          ?.filter((q) => onFilterDependency(qg, currentValues, q))
          ?.map((q) => ({
            ...q,
            group_id: qg?.id,
            group_name: qg?.name,
          }));

        if (transformedQuestions.length > 0) {
          return {
            ...translatedQg,
            ...repeat,
            ...repeats,
            id: qg?.id || qgi,
            question: transformedQuestions,
          };
        }
        return undefined;
      })
      .filter((qg) => qg)
      .filter((qg) => qg.question.length),
  };
};

export const modifyDependency = ({ question }, { dependency }, repeat) => {
  const questions = question.map((q) => q.id);
  return dependency.map((d) => {
    if (questions.includes(d.id) && repeat) {
      return { ...d, id: `${d.id}-${repeat}` };
    }
    return d;
  });
};

export const validateDependency = (dependency, value) => {
  if (dependency?.options && typeof value !== 'undefined') {
    const v = typeof value === 'string' ? [value] : value;
    return intersection(dependency.options, v)?.length > 0;
  }
  let valid = false;
  if (dependency?.min) {
    valid = value >= dependency.min;
  }
  if (dependency?.max) {
    valid = value <= dependency.max;
  }
  if (dependency?.equal) {
    valid = value === dependency.equal;
  }
  if (dependency?.notEqual) {
    valid = value !== dependency.notEqual && !!value;
  }
  return valid;
};

export const generateValidationSchemaFieldLevel = async (currentValue, field) => {
  const { label, type, required, rule } = field;
  const requiredError = `${label} is required.`;
  let yupType;
  switch (type) {
    case 'number':
      // number rules
      yupType = currentValue === '' ? Yup.string() : Yup.number();
      if (currentValue !== '' && rule?.min) {
        yupType = yupType.min(rule.min);
      }
      if (currentValue !== '' && rule?.max) {
        yupType = yupType.max(rule.max);
      }
      if (currentValue !== '' && !rule?.allowDecimal) {
        // by default decimal is allowed
        yupType = yupType.integer();
      }
      break;
    case 'date':
      if (currentValue === '') {
        yupType = Yup.string();
      } else {
        yupType = Yup.date();
      }
      break;
    case 'option':
      yupType = Yup.array().nullable();
      if (required) {
        yupType = Yup.array().min(1, requiredError);
      }
      break;
    case 'multiple_option':
      yupType = Yup.array().nullable();
      if (required) {
        yupType = Yup.array().min(1, requiredError);
      }
      break;
    case 'cascade':
      yupType = Yup.array();
      break;
    case 'geo':
      yupType = Yup.array();
      break;
    default:
      yupType = Yup.string();
      break;
  }
  if (required) {
    yupType = yupType.required(requiredError);
  }
  try {
    await yupType.validateSync(currentValue);
    return {
      [field?.id]: true,
    };
  } catch (error) {
    return {
      [field?.id]: error.message,
    };
  }
};

export const generateDataPointName = (forms, currentValues, cascades = {}) => {
  const dataPointNameValues = forms?.question_group?.length
    ? forms.question_group
        .filter((qg) => !qg?.repeatable)
        .flatMap((qg) => qg.question.filter((q) => q?.meta))
        ?.map((q) => {
          const defaultValue = currentValues?.[q.id] || null;
          const value = q.type === 'cascade' ? cascades?.[q.id] || defaultValue : defaultValue;
          return { id: q.id, type: q.type, value };
        })
    : [];
  const geoQuestion = forms?.question_group
    ?.flatMap((qg) => qg?.question)
    ?.find((q) => q?.type === 'geo');
  const dpName = dataPointNameValues
    .filter((d) => d.type !== 'geo' && (d.value || d.value === 0))
    .map((x) => x.value)
    .join(' - ');
  const [lat, lng] =
    dataPointNameValues.find((d) => d.type === 'geo')?.value ||
    currentValues?.[geoQuestion?.id] ||
    [];
  const dpGeo = lat && lng ? `${lat}|${lng}` : null;
  return { dpName, dpGeo };
};

export const getCurrentTimestamp = () => Math.floor(Date.now() / 1000);

export const getDurationInMinutes = (startTime) => {
  // Get the current timestamp in seconds
  const endTime = getCurrentTimestamp();
  // Calculate the duration in seconds
  const durationInSeconds = endTime - startTime;

  return Math.floor(durationInSeconds / 60);
};

const transformValue = (question, value, prefilled = []) => {
  const findPrefilled = prefilled.find((p) => p?.id === question?.id);
  const defaultEmpty = ['multiple_option', 'option'].includes(question?.type) ? [] : '';
  let answer = defaultEmpty;
  if (value || value === 0) {
    answer = value;
  }
  if (findPrefilled?.answer) {
    answer = findPrefilled.answer;
  }

  if (question?.type === 'cascade') {
    return [answer];
  }
  if (question?.type === 'geo') {
    return answer === '' ? [] : value;
  }
  if (question?.type === 'number' && typeof answer !== 'undefined') {
    return `${answer}`;
  }
  if (question?.default_value?.monitoring) {
    return ['multiple_option', 'option'].includes(question?.type)
      ? [question.default_value.monitoring]
      : question.default_value.monitoring;
  }
  return answer;
};

export const transformMonitoringData = (formDataJson, lastValues) => {
  const formData = JSON.parse(formDataJson.json);
  const allQuestions = formData?.question_group?.flatMap((qg) => qg?.question);
  const prefilled = allQuestions
    ?.filter((q) => lastValues?.[q?.id] && q?.pre)
    ?.filter((q) => lastValues[q.id] === q.pre.answer || lastValues[q.id].includes(q.pre.answer))
    ?.flatMap((q) => q?.pre?.fill || []);

  // Initialize with an empty object
  const currentValues = {};

  // Loop through the lastValues object keys
  if (lastValues && Object.keys(lastValues).length) {
    Object.keys(lastValues).forEach((key) => {
      const [questionId] = key.split('-');
      const question = allQuestions?.find((q) => `${q?.id}` === questionId);
      if (question) {
        currentValues[key] = transformValue(question, lastValues[key], prefilled);
      }
    });
  }

  const admQuestion = allQuestions.find(
    (q) => q?.type === 'cascade' && q?.source?.file === 'administrator.sqlite',
  );
  const prevAdmAnswer = lastValues?.[admQuestion?.id] ? [lastValues?.[admQuestion?.id]] : [];
  return { currentValues, prevAdmAnswer };
};

/**
 * Sanitizes the function string by removing any occurrences of "fetch" or "return fetch"
 * and replacing them with a console.error statement.
 */
const sanitize = [
  {
    prefix: /return fetch|fetch/g,
    re: /return fetch(\(.+)\} +|fetch(\(.+)\} +/,
    log: 'Fetch is not allowed.',
  },
];
/**
 * Checks if the function string contains any occurrences of "fetch" or "return fetch"
 * and replaces them with a console.error statement.
 * @param {string} fnString - The function string to check.
 * @returns
 */
const checkDirty = (fnString) =>
  sanitize.reduce((prev, sn) => {
    const dirty = prev.match(sn.re);
    if (dirty) {
      return prev.replace(sn.prefix, '').replace(dirty[1], `console.error("${sn.log}");`);
    }
    return prev;
  }, fnString);

/**
 * Fucntion to convert a function string into an array of tokens.
 * It handles hex color codes by temporarily replacing them with placeholders.
 * The function uses a regular expression to match various tokens, including
 * operators, numbers, and identifiers.
 * @param {string} fnString - The function string to be tokenized.
 * @returns
 */
const fnToArray = (fnString) => {
  // First handle hex color codes by temporarily replacing them
  const hexColorPattern = /"#[0-9A-Fa-f]{6}"/g;
  const hexColors = [];
  let modifiedString = fnString;

  // Extract and replace hex colors with placeholders
  let index = 0;
  let match = hexColorPattern.exec(fnString);
  while (match !== null) {
    const placeholder = `__HEX_COLOR_${index}__`;
    hexColors.push({ placeholder, value: match[0] });
    modifiedString = modifiedString.replace(match[0], placeholder);
    index += 1;
    match = hexColorPattern.exec(fnString);
  }

  // Normal tokenization
  const regex =
    // eslint-disable-next-line no-useless-escape
    /\#\d+|[(),?;&.'":()+\-*/.!]|<=|<|>|>=|!=|==|[||]{2}|=>|__HEX_COLOR_[0-9]+__|\w+| /g;
  const tokens = modifiedString.match(regex) || [];

  // Restore hex colors
  return tokens.map((token) => {
    const hexColor = hexColors.find((hc) => hc.placeholder === token);
    return hexColor ? hexColor.value : token;
  });
};

/**
 * Handles numeric values by removing quotes and trimming whitespace.
 * It uses a regular expression to check if the value is numeric.
 * If the value is numeric, it returns the trimmed value without quotes.
 * Otherwise, it returns the original value.
 * @param {*} val
 * @returns
 */
const handeNumericValue = (val) => {
  const regex = /^"\d+"$|^\d+$/;
  const isNumeric = regex.test(val);
  if (isNumeric) {
    return String(val).trim().replace(/['"]/g, '');
  }
  return val;
};

/**
 * Generates the function body by replacing placeholders with actual values.
 * It handles hex color codes, numeric values, and string values.
 * The function uses a regular expression to check if the processed string
 * matches a valid numeric format. If it does, it returns the generated function body.
 * If not, it returns a default value based on the original function string.
 * @param {*} fnMetadata
 * @param {*} values
 * @param {*} questions
 * @returns
 */
const generateFnBody = (fnMetadata, values, questions = []) => {
  if (!fnMetadata) {
    return false;
  }

  // Create a map of question names to IDs for faster lookup
  const questionMap = {};
  if (questions && questions.length) {
    questions.forEach((q) => {
      if (q.name && q.id) {
        questionMap[q.name] = q.id;
      }
    });
  }

  let defaultVal = null;
  // Replace variables with numeric placeholders
  let processedString = fnMetadata;
  // Iterate over keys of the values object and replace placeholders with '0'
  Object.keys(values).forEach((key) => {
    processedString = processedString.replace(new RegExp(`#${key}#`, 'g'), '0');
  });

  // Check if the processed string matches the regular expression
  const validNumericRegex = /^[\d\s+\-*/().]*$/;
  if (!validNumericRegex.test(processedString)) {
    // update defaultVal into empty string for non numeric equation
    defaultVal = fnMetadata.includes('!') ? String(null) : '';
  }

  const fnMetadataTemp = fnToArray(fnMetadata);

  // generate the fnBody
  const fnBody = fnMetadataTemp.map((f) => {
    // First check for literal hex color codes in quotes - don't process them
    if (f.startsWith('"#') && f.endsWith('"') && /^"#[0-9A-Fa-f]{6}"$/.test(f)) {
      return f; // Return hex color as-is
    }
    // Check if the token is a number or a string
    if (questionMap?.[f]) {
      let val = values?.[questionMap[f]];

      if (!val && val !== 0) {
        return defaultVal;
      }
      if (typeof val === 'object') {
        if (Array.isArray(val)) {
          val = val.join(',');
        } else if (val?.lat) {
          val = `${val.lat},${val.lng}`;
        } else {
          val = defaultVal;
        }
      }
      if (typeof val === 'number') {
        val = Number(val);
      }
      if (typeof val === 'string') {
        val = `"${val}"`;
      }

      return val;
    }
    return f;
  });

  // all fn conditions meet, return generated fnBody
  if (!fnBody.filter((x) => !x).length) {
    return fnBody
      .map(handeNumericValue)
      .join('')
      .replace(/(?:^|\s)\.includes\(['"][^'"]+['"]\)/g, "''$1")
      .replace(/''\s*\./g, "''.");
  }

  // remap fnBody if only one fnBody meet the requirements
  return fnBody
    .filter((x) => x)
    .map(handeNumericValue)
    .join('')
    .replace(/(?:^|\s)\.includes\(['"][^'"]+['"]\)/g, " ''$&")
    .replace(/''\s*\./g, "''.");
};

/**
 * Function to fix incomplete math operations in a string expression.
 * It checks if the expression ends with an incomplete math operation
 * (e.g., '+', '-', '*', '/') and appends '0' to complete the operation.
 * If the expression ends with '*' or '/', it removes the operator.
 * @param {string} expression - The string expression to be fixed.
 * @returns
 */
const fixIncompleteMathOperation = (expression) => {
  // Regular expression to match incomplete math operations
  const incompleteMathRegex = /[+\-*/]\s*$/;

  // Check if the input ends with an incomplete math operation
  if (incompleteMathRegex.test(expression)) {
    // If the expression ends with '+' or '-', append '0' to complete the operation
    if (expression.trim().endsWith('+') || expression.trim().endsWith('-')) {
      return `${expression.trim()}0`;
    }
    // If the expression ends with '*' or '/', it's safer to remove the operator
    if (expression.trim().endsWith('*') || expression.trim().endsWith('/')) {
      return expression.trim().slice(0, -1);
    }
  }
  return expression;
};
/**
 * Function to convert a function string into an actual function.
 * It sanitizes the function string, generates the function body,
 * and creates a new function using the Function constructor.
 * If an error occurs during the process, it returns null.
 * @param {string} fnString - The function string to be converted.
 * @param {object} values - An object containing values to be used in the function.
 * @param {array} questions - An array of question objects to be used in the function.
 * @returns {function|null} - The generated function or null if an error occurs.
 * @throws {Error} - Throws an error if the function string is invalid or if the function cannot be created.
 */
export const strToFunction = (fnString, values, questions = []) => {
  try {
    const fnStr = checkDirty(fnString);
    const fnBody = fixIncompleteMathOperation(generateFnBody(fnStr, values, questions));
    // eslint-disable-next-line no-new-func
    return new Function(`return ${fnBody}`);
  } catch {
    return null;
  }
};
