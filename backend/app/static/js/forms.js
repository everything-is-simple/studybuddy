/**
 * forms.js - 表单验证和处理模块
 * 提供统一的表单验证、数据提取和错误处理
 */
const sbForm = {
  /**
   * 验证必填字段
   * @param {string|HTMLInputElement|HTMLTextAreaElement} field - 字段选择器或元素
   * @returns {boolean} - 是否有效（非空且trim后非空）
   */
  required(field) {
    const el = typeof field === 'string' ? document.querySelector(field) : field;
    if (!el) return false;
    const value = el.value;
    return typeof value === 'string' && value.trim().length > 0;
  },

  /**
   * 获取字段的trim值
   * @param {string|HTMLInputElement|HTMLTextAreaElement} field - 字段选择器或元素
   * @returns {string} - trim后的值
   */
  value(field) {
    const el = typeof field === 'string' ? document.querySelector(field) : field;
    if (!el) return '';
    return (el.value || '').trim();
  },

  /**
   * 获取数字字段的值
   * @param {string|HTMLInputElement} field - 字段选择器或元素
   * @returns {number|null} - 数字值，或null如果无效
   */
  number(field) {
    const el = typeof field === 'string' ? document.querySelector(field) : field;
    if (!el) return null;
    const num = Number(el.value);
    return isNaN(num) ? null : num;
  },

  /**
   * 验证并提取多个必填字段
   * @param {Object.<string, string>} fields - 字段映射 {key: selector}
   * @returns {{valid: boolean, data: Object, missing: string[]}} - 验证结果和数据
   */
  validateRequired(fields) {
    const data = {};
    const missing = [];
    
    for (const [key, selector] of Object.entries(fields)) {
      const value = this.value(selector);
      if (!value) {
        missing.push(key);
      }
      data[key] = value;
    }
    
    return {
      valid: missing.length === 0,
      data,
      missing
    };
  },

  /**
   * 从表单提取数据（可选字段支持）
   * @param {Object.<string, string>} fields - 字段映射 {key: selector}
   * @returns {Object} - 提取的数据对象
   */
  extract(fields) {
    const data = {};
    for (const [key, selector] of Object.entries(fields)) {
      data[key] = this.value(selector);
    }
    return data;
  },

  /**
   * 清空表单字段
   * @param {string[]|HTMLElement[]} fields - 字段选择器或元素数组
   */
  clear(fields) {
    fields.forEach(field => {
      const el = typeof field === 'string' ? document.querySelector(field) : field;
      if (el) el.value = '';
    });
  },

  /**
   * 禁用/启用表单字段
   * @param {string[]|HTMLElement[]} fields - 字段选择器或元素数组
   * @param {boolean} disabled - 是否禁用
   */
  setDisabled(fields, disabled) {
    fields.forEach(field => {
      const el = typeof field === 'string' ? document.querySelector(field) : field;
      if (el) el.disabled = disabled;
    });
  },

  /**
   * 解析逗号分隔的ID列表
   * @param {string} value - 逗号分隔的字符串
   * @returns {string[]} - trim后的非空ID数组
   */
  parseIds(value) {
    if (!value) return [];
    return value.split(',').map(id => id.trim()).filter(Boolean);
  },

  /**
   * 显示字段错误（通过设置aria-invalid和添加错误类）
   * @param {string|HTMLElement} field - 字段选择器或元素
   * @param {boolean} isError - 是否有错误
   */
  showError(field, isError) {
    const el = typeof field === 'string' ? document.querySelector(field) : field;
    if (!el) return;
    
    if (isError) {
      el.setAttribute('aria-invalid', 'true');
      el.classList.add('field-error');
    } else {
      el.removeAttribute('aria-invalid');
      el.classList.remove('field-error');
    }
  },

  /**
   * 简化的表单提交处理
   * @param {HTMLFormElement} form - 表单元素
   * @param {Object} config - 配置对象
   * @param {Object.<string, string>} config.fields - 必填字段映射
   * @param {Function} config.onValid - 验证通过时的处理函数，接收data参数
   * @param {Function} [config.onInvalid] - 验证失败时的处理函数，接收missing参数
   * @param {boolean} [config.clearOnSuccess=false] - 成功后是否清空表单
   */
  handle(form, config) {
    const { fields, onValid, onInvalid, clearOnSuccess = false } = config;
    
    form.onsubmit = async (event) => {
      event.preventDefault();
      
      const result = this.validateRequired(fields);
      
      if (!result.valid) {
        if (onInvalid) {
          onInvalid(result.missing);
        }
        return;
      }
      
      try {
        await onValid(result.data);
        if (clearOnSuccess) {
          this.clear(Object.values(fields));
        }
      } catch (error) {
        // 错误由onValid处理
        throw error;
      }
    };
  }
};
