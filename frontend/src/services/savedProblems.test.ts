import { describe, it, expect } from 'vitest';
import { exerciseRef, nvoRef, refKey } from './savedProblems';

describe('saved problem reference keys', () => {
  it('builds an exercise ref from the durable row id', () => {
    expect(exerciseRef(4271)).toBe('4271');
  });

  it('builds an NVO ref from the exam id and question number', () => {
    expect(nvoRef('exam-abc', 7)).toBe('exam-abc:7');
  });

  it('namespaces a ref key by source so the two sources cannot collide', () => {
    expect(refKey('exercise', '4271')).toBe('exercise:4271');
    expect(refKey('nvo', 'exam-abc:7')).toBe('nvo:exam-abc:7');
  });
});
