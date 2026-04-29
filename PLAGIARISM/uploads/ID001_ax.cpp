#include <iostream>
using namespace std;

float doMath(float a, float b, char c) {
  if (c == '+')
    return a + b;
  else if (c == '-')
    return a - b;
  else if (c == '*')
    return a * b;
  else if (c == '/')
    return (b != 0) ? a / b : 0;
  return 0;
}

int main() {
  cout << doMath(10, 5, '+') << endl;
  return 0;
}
