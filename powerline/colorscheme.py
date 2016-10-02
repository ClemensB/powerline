# vim:fileencoding=utf-8:noet
from __future__ import (unicode_literals, division, absolute_import, print_function)

from copy import copy

from powerline.lib.colors  import cterm_to_srgb, srgb_to_cterm, srgb_lerp
from powerline.lib.unicode import unicode


DEFAULT_MODE_KEY = None
ATTR_BOLD = 1
ATTR_ITALIC = 2
ATTR_UNDERLINE = 4


def get_attrs_flag(attrs):
	'''Convert an attribute array to a renderer flag.'''
	attrs_flag = 0
	if 'bold' in attrs:
		attrs_flag |= ATTR_BOLD
	if 'italic' in attrs:
		attrs_flag |= ATTR_ITALIC
	if 'underline' in attrs:
		attrs_flag |= ATTR_UNDERLINE
	return attrs_flag


def pick_gradient_value(grad_list, gradient_level):
	'''Given a list of colors and gradient percent, return a color that should be used.

	Note: gradient level is not checked for being inside [0, 100] interval.
	'''
	return grad_list[int(round(gradient_level * (len(grad_list) - 1) / 100))]

def pick_interpolated_gradient(gradient, gradient_level):
	'''Given a list of gradient stops and gradient percent, return a color that should be used.

	Note: gradient level is not checked for being inside [0, 100] interval.'''
	gradient_level /= 100.

	# Find current segment of gradient
	segment_start = None
	segment_end   = None
	for i in range(len(gradient)):
		if gradient_level >= gradient[i][0]:
			segment_start = gradient[i]
			segment_end   = gradient[i + 1]
			break

	x = (gradient_level - segment_start[0]) / (segment_end[0] - segment_start[0])

	return  srgb_lerp(segment_start[1], segment_end[1], x)

class Colorscheme(object):
	def __init__(self, colorscheme_config, colors_config):
		'''Initialize a colorscheme.'''
		self.colors = {}
		self.gradients = {}
		self.interpolated_gradients = {}

		self.groups = colorscheme_config['groups']
		self.translations = colorscheme_config.get('mode_translations', {})

		# Create a dict of color tuples with both a cterm and hex value
		for color_name, color in colors_config['colors'].items():
			try:
				self.colors[color_name] = (color[0], int(color[1], 16))
			except TypeError:
				self.colors[color_name] = (color, cterm_to_srgb(color))

		# Create a dict of gradient names with two lists: for cterm and hex 
		# values. Two lists in place of one list of pairs were chosen because 
		# true colors allow more precise gradients.
		for gradient_name, gradient in colors_config['gradients'].items():
			if len(gradient) == 2:
				self.gradients[gradient_name] = (
					(gradient[0], [int(color, 16) for color in gradient[1]]))
			else:
				self.gradients[gradient_name] = (
					(gradient[0], [cterm_to_srgb(color) for color in gradient[0]]))

		if not 'interpolated_gradients' in colors_config:
			return

		# Create a dict of gradient names with a list of gradient stops
		# Each stop contains a position (between 0.0 and 1,9) and the associated color.
		# The first stop must have the position 0.0 and the last stop must have the position 1.0.
		# The position of the stops has to be sorted ascending.
		# Colors given as cterm indexes will be converted to sRGB colors.
		for gradient_name, gradient in colors_config['interpolated_gradients'].items():
			assert gradient[0][0] == 0.0 and gradient[-1][0] == 1.0
			steps = []
			last_step = -1.0
			for step in gradient:
				assert step[0] > last_step
				steps.append((step[0], int(step[1], 16) if type(step[1]) == str else cterm_to_srgb(step[1])))
				last_step = step[0]
			self.interpolated_gradients[gradient_name] = steps

	def get_gradient(self, gradient, gradient_level):
		if gradient in self.interpolated_gradients:
			rgb = pick_interpolated_gradient(self.interpolated_gradients[gradient], gradient_level)
			return srgb_to_cterm(rgb), rgb

		if gradient in self.gradients:
			return tuple((pick_gradient_value(grad_list, gradient_level) for grad_list in self.gradients[gradient]))
		else:
			return self.colors[gradient]

	def get_group_props(self, mode, trans, group, translate_colors=True):
		if isinstance(group, (str, unicode)):
			try:
				group_props = trans['groups'][group]
			except KeyError:
				try:
					group_props = self.groups[group]
				except KeyError:
					return None
				else:
					return self.get_group_props(mode, trans, group_props, True)
			else:
				return self.get_group_props(mode, trans, group_props, False)
		else:
			if translate_colors:
				group_props = copy(group)
				try:
					ctrans = trans['colors']
				except KeyError:
					pass
				else:
					for key in ('fg', 'bg'):
						try:
							group_props[key] = ctrans[group_props[key]]
						except KeyError:
							pass
				return group_props
			else:
				return group

	def get_highlighting(self, groups, mode, gradient_level=None):
		trans = self.translations.get(mode, {})
		for group in groups:
			group_props = self.get_group_props(mode, trans, group)
			if group_props:
				break
		else:
			raise KeyError('Highlighting groups not found in colorscheme: ' + ', '.join(groups))

		if gradient_level is None:
			pick_color = self.colors.__getitem__
		else:
			pick_color = lambda gradient: self.get_gradient(gradient, gradient_level)

		return {
			'fg': pick_color(group_props['fg']),
			'bg': pick_color(group_props['bg']),
			'attrs': get_attrs_flag(group_props.get('attrs', [])),
		}
